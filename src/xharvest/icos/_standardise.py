"""Convert FLUXNET archives from the ICOS Carbon Portal into a standardised Dataset.

Only the daily (`DD`) files are read, and only a fixed set of variables for soil
moisture and ecosystem carbon modelling: see `SCALARS`, `PROFILES` and `QC`. The
result has dims `(time, site)`, plus `depth` for the soil profiles. Variables keep
FLUXNET's names and units, with the unit strings renamed to their CF equivalents
(`deg C` becomes `degC`); fill values become NaN, and nothing else about the values
changes.

A daily value covers the site's local standard day, which starts at
`00:00 - UTC_OFFSET` in UTC; `time` is that start, and `time_bounds` the day.

Examples:
    >>> from pathlib import Path
    >>> from xharvest.icos import to_netcdf
    >>> to_netcdf(Path("data/icos").glob("*.zip"), "data/icos.nc")  # doctest: +SKIP
"""

from collections import defaultdict
from collections.abc import Iterable
from os import PathLike
from pathlib import Path

import numpy as np
import xarray as xr

from .. import __version__
from .._fluxnet import Archive, read_daily
from ..errors import ProviderError
from ..provenance import history_line, is_sidecar, read_sidecar, utc_now
from ._fetch import DATA_URL

SCALARS = {
    # Meteorology
    "TA_F": "degC",
    "VPD_F": "hPa",
    "P_F": "mm d-1",
    "SW_IN_F": "W m-2",
    "LW_IN_F": "W m-2",
    "PA_F": "kPa",
    "WS_F": "m s-1",
    "PPFD_IN": "umol m-2 s-1",
    "NETRAD": "W m-2",
    "CO2_F_MDS": "umol mol-1",
    # Soil heat flux
    "G_F_MDS": "W m-2",
    # Energy and water
    "LE_F_MDS": "W m-2",
    "LE_CORR": "W m-2",
    "LE_CORR_JOINTUNC": "W m-2",
    "H_F_MDS": "W m-2",
    "H_CORR": "W m-2",
    # Carbon
    "NEE_VUT_REF": "g m-2 d-1",
    "NEE_VUT_REF_JOINTUNC": "g m-2 d-1",
    "GPP_NT_VUT_REF": "g m-2 d-1",
    "GPP_DT_VUT_REF": "g m-2 d-1",
    "RECO_NT_VUT_REF": "g m-2 d-1",
    "RECO_DT_VUT_REF": "g m-2 d-1",
}
"""Variables on `(time, site)`, with the CF unit each must have."""

PROFILES = {"SWC_F_MDS": "%", "TS_F_MDS": "degC"}
"""Soil profiles, stacked from `<name>_<n>` onto `(time, site, depth)`."""

QC = [
    "TA_F",
    "VPD_F",
    "P_F",
    "SW_IN_F",
    "LW_IN_F",
    "PA_F",
    "WS_F",
    "PPFD_IN",
    "NETRAD",
    "CO2_F_MDS",
    "G_F_MDS",
    "LE_F_MDS",
    "H_F_MDS",
    "NEE_VUT_REF",
    *PROFILES,
]
"""Variables whose `_QC` is kept: the fraction of the day's half-hours that were
measured or gap-filled with good quality.

`BIFVARINFO` gives some `_QC` columns the parent variable's unit and definition
(`SWC_F_MDS_1_QC` as `%`, "Soil water content, ..."), though their values are 0-1
fractions like every other daily `_QC`. So every `_QC` gets unit `1`, its values
are checked to lie in 0-1, and its description is `QC_DESCRIPTION`.
"""

QC_DESCRIPTION = (
    "Quality flag for {}: fraction between 0 and 1 of the day's half-hours that "
    "were measured or gap-filled with good quality"
)

NOT_MEANS = {"LE_CORR", "H_CORR", "LE_CORR_JOINTUNC", "NEE_VUT_REF_JOINTUNC"}
"""Variables given no `cell_methods`, as not the daily mean of half-hourly values.

The others were each checked to be, against the half-hourly file at two sites; see
the provider page. The uncertainties are not means. `LE_CORR` and `H_CORR` are
defined as "average from half-hourly data", but differ from the mean of half-hourly
`LE_CORR` and `H_CORR` by up to 51 W m-2 at UK-Cvn.
"""

TITLE = "FLUXNET daily data from the ICOS Carbon Portal"

_DAY = np.timedelta64(1, "D")


def _attrs(name: str, archives: list[Archive], units: str) -> dict[str, str]:
    """Attributes of a variable, from the first archive that describes it."""
    attrs = {"units": units}
    if name.endswith("_QC"):
        # BIFVARINFO describes some _QC columns as their parent variable, so
        # describe them all from what the values were checked to be.
        attrs["description"] = QC_DESCRIPTION.format(name.removesuffix("_QC"))
        return attrs
    for archive in archives:
        if name in PROFILES:
            depths = archive.profile(name)
            if not depths:
                continue
            source = archive.variables[next(iter(depths.values()))]
        elif name in archive.variables:
            source = archive.variables[name]
        else:
            continue
        attrs["provider_units"] = source.units
        attrs["description"] = source.definition
        break
    if name not in NOT_MEANS:
        attrs["cell_methods"] = "time: mean"
    return attrs


def _column(archive: Archive, name: str, units: str) -> np.ndarray:
    if name not in archive.columns:
        return np.full(len(archive.dates), np.nan)
    values = archive.columns[name]
    if name.endswith("_QC"):
        # Their units in BIFVARINFO are unreliable (see `QC`); their values are not.
        if np.any((values < 0) | (values > 1)):
            raise ProviderError(
                f"{archive.site}: {name} has values outside 0-1, so it is not the "
                "fraction a daily _QC should be"
            )
        return values
    found = archive.variables[name].cf_units
    if found != units:
        raise ProviderError(
            f"{archive.site}: {name} has unit {archive.variables[name].units!r} "
            f"({found}), not {units}"
        )
    return values


def _site_dataset(archive: Archive) -> xr.Dataset:
    profiles = {base: archive.profile(base) for base in PROFILES}
    depths = sorted({d for depth_map in profiles.values() for d in depth_map})
    n = len(archive.dates)

    data_vars = {}
    for name, units in SCALARS.items():
        data_vars[name] = (("time", "site"), _column(archive, name, units)[:, None])
    for base in QC:
        if base not in PROFILES:
            values = _column(archive, f"{base}_QC", "1")
            data_vars[f"{base}_QC"] = (("time", "site"), values[:, None])
    for base, units in PROFILES.items():
        values = np.full((n, 1, len(depths)), np.nan)
        flags = np.full((n, 1, len(depths)), np.nan)
        for depth, name in profiles[base].items():
            i = depths.index(depth)
            values[:, 0, i] = _column(archive, name, units)
            flags[:, 0, i] = _column(archive, f"{name}_QC", "1")
        data_vars[base] = (("time", "site", "depth"), values)
        data_vars[f"{base}_QC"] = (("time", "site", "depth"), flags)

    return xr.Dataset(
        data_vars,
        coords={
            "time": archive.time,
            "site": [archive.site],
            "depth": np.array(depths, dtype=float),
            "site_name": ("site", [archive.site_name]),
            "lat": ("site", [archive.lat]),
            "lon": ("site", [archive.lon]),
            "altitude": (
                "site",
                [np.nan if archive.elevation is None else archive.elevation],
            ),
            "utc_offset": ("site", [archive.utc_offset]),
            "igbp": ("site", [archive.igbp]),
            "network": ("site", [archive.network]),
        },
    )


def _combine_pieces(site: str, pieces: list[xr.Dataset]) -> xr.Dataset:
    """Join one site's record from archives of different releases.

    Where they overlap, they must agree wherever both have a value.
    """
    if len(pieces) == 1:
        return pieces[0]
    try:
        return xr.merge(
            pieces, compat="no_conflicts", join="outer", combine_attrs="override"
        )
    except xr.MergeError as err:
        raise ValueError(
            f"archives for site {site} disagree where they overlap, as releases "
            f"that revised the data do; standardise one release at a time ({err})"
        ) from None


def standardise(paths: Iterable[str | PathLike]) -> xr.Dataset:
    """Combine FLUXNET archives from the ICOS Carbon Portal into one daily Dataset.

    Args:
        paths: ZIP archives written by `xharvest.icos.fetch`. Provenance
            sidecars among them are skipped, so a glob over the download
            directory works.

    Returns:
        A Dataset with dims `(time, site, depth)`. `depth` is the union of the
        sites' soil sensor depths, in metres below ground; only the soil
        profiles use it. Sites are outer-joined on time and depth, so a site
        with a shorter record or fewer sensors is NaN-padded, and a variable a
        site does not measure is NaN there.

    Raises:
        ValueError: If no archives are given, the sites' UTC offsets differ, or
            two archives for one site disagree where they overlap.
        FileNotFoundError: If an archive has no provenance sidecar.
        ProviderError: If an archive is not one the connector can read, or a
            variable has a unit other than the one in `SCALARS` or `PROFILES`.
    """
    paths = sorted(Path(p) for p in paths if not is_sidecar(p))
    if not paths:
        raise ValueError("no ICOS FLUXNET archives to standardise")

    archives: list[Archive] = []
    retrievals = []
    pieces: dict[str, list[xr.Dataset]] = defaultdict(list)
    for path in paths:
        retrieval = read_sidecar(path)
        archive = read_daily(path)
        retrievals.append(retrieval)
        archives.append(archive)
        pieces[archive.site].append(_site_dataset(archive))

    offsets = {a.utc_offset for a in archives}
    if len(offsets) > 1:
        by_offset = sorted({(a.utc_offset, a.site) for a in archives})
        listed = ", ".join(f"{site} (UTC{offset:+g})" for offset, site in by_offset)
        raise ValueError(
            "the sites keep different local standard times, so their days do not "
            f"line up: {listed}; standardise sites with one UTC offset at a time"
        )

    sites = [_combine_pieces(site, site_pieces) for site, site_pieces in pieces.items()]
    ds = xr.concat(
        sites, dim="site", join="outer", combine_attrs="override", data_vars="all"
    )
    ds = ds.sortby("time").sortby("depth")

    for name in ds.data_vars:
        base = str(name).removesuffix("_QC")
        units = "1" if str(name).endswith("_QC") else {**SCALARS, **PROFILES}[base]
        ds[name].attrs = _attrs(str(name), archives, units)

    start = ds.time.values
    ds = ds.assign_coords(
        time_bounds=(("time", "nv"), np.stack([start, start + _DAY], axis=-1))
    )
    # One encoding for both, so time and its bounds share units as CF requires.
    ds.time.encoding["units"] = "minutes since 1970-01-01 00:00:00"
    ds.time.attrs.update(
        standard_name="time",
        long_name="time (UTC) at the start of the site's local standard day",
        bounds="time_bounds",
    )
    ds.depth.attrs.update(
        standard_name="depth",
        long_name="depth of soil sensor below the surface",
        units="m",
        positive="down",
    )
    ds.site.attrs.update(long_name="FLUXNET site code", cf_role="timeseries_id")
    ds.site_name.attrs.update(long_name="site name")
    ds.lat.attrs.update(standard_name="latitude", units="degrees_north")
    ds.lon.attrs.update(standard_name="longitude", units="degrees_east")
    ds.altitude.attrs.update(
        standard_name="height_above_mean_sea_level",
        units="m",
        comment="LOCATION_ELEV from the archive's site metadata",
    )
    ds.utc_offset.attrs.update(
        long_name="offset of the data's local standard time from UTC", units="h"
    )
    ds.igbp.attrs.update(long_name="IGBP land cover class")
    ds.network.attrs.update(long_name="FLUXNET network that prepared the data")

    history = sorted(history_line(r) for r in retrievals)
    history.append(f"{utc_now()} standardised (xharvest {__version__})")
    citations = sorted({r.metadata.get("citation", "") for r in retrievals} - {""})
    versions = ", ".join(sorted({a.oneflux_version for a in archives}))
    ds.attrs = {
        "title": TITLE,
        "institution": "; ".join(
            sorted(
                {
                    f"{a.network} network, processed by {a.processing_center}"
                    for a in archives
                }
            )
        ),
        "source": f"FLUXNET data product (ONEFlux {versions}), ICOS Carbon Portal, "
        f"{DATA_URL}",
        "license": "; ".join(sorted({a.licence for a in archives})),
        "references": "\n".join(citations),
        "history": "\n".join(history),
    }
    return ds


def to_netcdf(paths: Iterable[str | PathLike], out: str | PathLike) -> Path:
    """Standardise FLUXNET archives and write the result to netCDF.

    Args:
        paths: As for `standardise`.
        out: The netCDF file to write; its directory is created if missing.

    Returns:
        The path written.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    standardise(paths).to_netcdf(out)
    return out
