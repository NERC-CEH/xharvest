"""Nodes that standardise FLUXNET archives from the ICOS Carbon Portal.

`standardise` builds its graph from these and the shared FLUXNET reader in
`xharvest._fluxnet`, and computes `dataset` from `paths`. Every node acts on all
the archives at once; most take and return a mapping from archive path to that
archive's part.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr
from hamilton.function_modifiers import tag

from .. import __version__
from .._fluxnet import Site, Table, Variable
from ..errors import ProviderError
from ..provenance import Retrieval, history_line, is_sidecar, read_sidecar, utc_now
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
measured or gap-filled with good quality."""

QC_DESCRIPTION = (
    "Quality flag for {}: fraction between 0 and 1 of the day's half-hours that "
    "were measured or gap-filled with good quality"
)

NOT_MEANS = {"LE_CORR", "H_CORR", "LE_CORR_JOINTUNC", "NEE_VUT_REF_JOINTUNC"}
"""Variables given no `cell_methods`, as not the daily mean of half-hourly values."""

TITLE = "FLUXNET daily data from the ICOS Carbon Portal"

_DAY = np.timedelta64(1, "D")


@tag(action="selects")
def archive_paths(paths: list[Path]) -> list[Path]:
    """Keep the archives among `paths`, sorted, and drop provenance sidecars.

    So a glob over the download directory works.

    Raises:
        ValueError: If no archives remain.
    """
    archives = sorted(p for p in paths if not is_sidecar(p))
    if not archives:
        raise ValueError("no ICOS FLUXNET archives to standardise")
    return archives


@tag(action="reads")
def retrievals(archive_paths: list[Path]) -> dict[Path, Retrieval]:
    """Read each archive's provenance sidecar, written by `fetch`.

    The sidecar records where and when the archive was downloaded, and the
    citation the portal gives for it, none of which the archive itself holds.

    Raises:
        FileNotFoundError: If an archive has no sidecar.
    """
    return {path: read_sidecar(path) for path in archive_paths}


@tag(action="selects")
def profiled_variables() -> tuple[str, ...]:
    """The soil profiles to stack on `depth`: `SWC_F_MDS` and `TS_F_MDS`."""
    return tuple(PROFILES)


@tag(action="selects")
def kept_variables(
    variables: dict[Path, dict[str, Variable]],
    described_tables: dict[Path, Table],
    soil_profiles: dict[Path, dict[str, dict[float, str]]],
) -> dict[Path, dict[str, Variable]]:
    """Keep the variables in `SCALARS`, and each sensor of the soil profiles.

    Every other column is dropped, including all `_QC` columns, which
    `kept_flags` keeps separately. A kept variable a site lacks is left out
    here and becomes NaN in `site_datasets`.
    """
    result = {}
    for path, table in described_tables.items():
        names = [name for name in SCALARS if name in table.columns]
        for depths in soil_profiles[path].values():
            names.extend(depths.values())
        result[path] = {name: variables[path][name] for name in names}
    return result


@tag(action="selects")
def kept_flags(
    described_tables: dict[Path, Table],
    soil_profiles: dict[Path, dict[str, dict[float, str]]],
) -> dict[Path, list[str]]:
    """Keep the `_QC` columns of the variables in `QC`, and of each soil sensor."""
    result = {}
    for path, table in described_tables.items():
        names = [f"{base}_QC" for base in QC if base not in PROFILES]
        for depths in soil_profiles[path].values():
            names.extend(f"{column}_QC" for column in depths.values())
        result[path] = [name for name in names if name in table.columns]
    return result


@tag(action="checks")
def checked_units(
    cf_units: dict[Path, dict[str, str]],
    kept_variables: dict[Path, dict[str, Variable]],
    soil_profiles: dict[Path, dict[str, dict[float, str]]],
) -> dict[Path, dict[str, str]]:
    """Check that each kept variable has the CF unit `SCALARS` or `PROFILES` expects.

    Raises:
        ProviderError: If a variable's unit, renamed to CF, is another.
    """
    for path, units in cf_units.items():
        expected = dict(SCALARS)
        for base, depths in soil_profiles[path].items():
            expected.update(dict.fromkeys(depths.values(), PROFILES[base]))
        for name, found in units.items():
            if found != expected[name]:
                raise ProviderError(
                    f"{path}: {name} has unit {kept_variables[path][name].units!r} "
                    f"({found}), not {expected[name]}"
                )
    return cf_units


@tag(action="checks")
def checked_flags(
    described_tables: dict[Path, Table], kept_flags: dict[Path, list[str]]
) -> dict[Path, Table]:
    """Check that every kept `_QC` value lies between 0 and 1.

    The archive's variable list gives some `_QC` columns their parent's unit
    and definition (`SWC_F_MDS_1_QC` as `%`), so it cannot say what they are;
    their values can. A daily `_QC` should be a fraction.

    Raises:
        ProviderError: If a kept `_QC` has a value outside 0-1.
    """
    for path, names in kept_flags.items():
        for name in names:
            values = described_tables[path].columns[name]
            if np.any((values < 0) | (values > 1)):
                raise ProviderError(
                    f"{path}: {name} has values outside 0-1, so it is not the "
                    "fraction a daily _QC should be"
                )
    return described_tables


@tag(action="checks")
def checked_sites(sites: dict[Path, Site]) -> dict[Path, Site]:
    """Check that every site keeps the same local standard time.

    A daily value covers the site's local day, so sites with different UTC
    offsets have days that start at different times, and cannot share a time
    axis.

    Raises:
        ValueError: If the sites' UTC offsets differ.
    """
    if len({site.utc_offset for site in sites.values()}) > 1:
        by_offset = sorted({(s.utc_offset, s.site) for s in sites.values()})
        listed = ", ".join(f"{site} (UTC{offset:+g})" for offset, site in by_offset)
        raise ValueError(
            "the sites keep different local standard times, so their days do not "
            f"line up: {listed}; standardise sites with one UTC offset at a time"
        )
    return sites


@tag(action="reshapes")
def site_datasets(
    checked_flags: dict[Path, Table],
    times: dict[Path, np.ndarray],
    soil_profiles: dict[Path, dict[str, dict[float, str]]],
    checked_sites: dict[Path, Site],
) -> dict[Path, xr.Dataset]:
    """Arrange each archive's kept columns into a Dataset with one site.

    Variables in `SCALARS` and their `_QC` go on `(time, site)`. Each soil
    profile's sensors are stacked on `(time, site, depth)`, over the depths of
    either profile at that site. A kept variable the site lacks, and a depth it
    has no sensor of that variable at, are NaN.
    """

    def column(table: Table, name: str) -> np.ndarray:
        if name in table.columns:
            return table.columns[name]
        return np.full(len(table.dates), np.nan)

    result = {}
    for path, table in checked_flags.items():
        profiles = soil_profiles[path]
        depths = sorted({d for depth_map in profiles.values() for d in depth_map})
        n = len(table.dates)
        data_vars = {}
        for name in SCALARS:
            data_vars[name] = (("time", "site"), column(table, name)[:, None])
        for base in QC:
            if base not in PROFILES:
                values = column(table, f"{base}_QC")[:, None]
                data_vars[f"{base}_QC"] = (("time", "site"), values)
        for base in PROFILES:
            values = np.full((n, 1, len(depths)), np.nan)
            flags = np.full((n, 1, len(depths)), np.nan)
            for depth, name in profiles[base].items():
                i = depths.index(depth)
                values[:, 0, i] = column(table, name)
                flags[:, 0, i] = column(table, f"{name}_QC")
            data_vars[base] = (("time", "site", "depth"), values)
            data_vars[f"{base}_QC"] = (("time", "site", "depth"), flags)
        site = checked_sites[path]
        result[path] = xr.Dataset(
            data_vars,
            coords={
                "time": times[path],
                "site": [site.site],
                "depth": np.array(depths, dtype=float),
                "site_name": ("site", [site.site_name]),
                "lat": ("site", [site.lat]),
                "lon": ("site", [site.lon]),
                "altitude": (
                    "site",
                    [np.nan if site.elevation is None else site.elevation],
                ),
                "utc_offset": ("site", [site.utc_offset]),
                "igbp": ("site", [site.igbp]),
                "network": ("site", [site.network]),
            },
        )
    return result


@tag(action="reshapes")
def site_records(
    site_datasets: dict[Path, xr.Dataset], checked_sites: dict[Path, Site]
) -> list[xr.Dataset]:
    """Join each site's archives into one record, a site per Dataset.

    Archives of one site from different releases are outer-joined on time.

    Raises:
        ValueError: If two archives of one site disagree where both have a
            value, as releases that revised the data do.
    """
    pieces: dict[str, list[xr.Dataset]] = defaultdict(list)
    for path, ds in site_datasets.items():
        pieces[checked_sites[path].site].append(ds)
    records = []
    for site, site_pieces in pieces.items():
        if len(site_pieces) == 1:
            records.append(site_pieces[0])
            continue
        try:
            records.append(
                xr.merge(
                    site_pieces,
                    compat="no_conflicts",
                    join="outer",
                    combine_attrs="override",
                )
            )
        except xr.MergeError as err:
            raise ValueError(
                f"archives for site {site} disagree where they overlap, as releases "
                f"that revised the data do; standardise one release at a time ({err})"
            ) from None
    return records


@tag(action="reshapes")
def combined(site_records: list[xr.Dataset]) -> xr.Dataset:
    """Join the sites on `time` and `depth`, padding each with NaN.

    A site with a shorter record, or fewer soil sensors, is NaN where it has no
    value, so every site has the same variables, times and depths.
    """
    ds = xr.concat(
        site_records,
        dim="site",
        join="outer",
        combine_attrs="override",
        data_vars="all",
    )
    return ds.sortby("time").sortby("depth")


@tag(action="interprets")
def descriptions(
    kept_variables: dict[Path, dict[str, Variable]],
    soil_profiles: dict[Path, dict[str, dict[float, str]]],
) -> dict[str, dict[str, str]]:
    """Take each variable's unit string and definition from one archive.

    A judgement: they come from the first archive, in path order, that has the
    variable, and for a soil profile from its shallowest sensor there. Other
    archives' wordings are not kept. A variable no archive has gets neither.

    Returns:
        `{variable: {"provider_units": ..., "description": ...}}`.
    """
    result: dict[str, dict[str, str]] = {}
    for path, kept in kept_variables.items():
        sources = {name: name for name in SCALARS}
        for base, depths in soil_profiles[path].items():
            if depths:
                sources[base] = next(iter(depths.values()))
        for name, column in sources.items():
            if name in result or column not in kept:
                continue
            variable = kept[column]
            result[name] = {
                "provider_units": variable.units,
                "description": variable.definition,
            }
    return result


@tag(action="interprets")
def flag_attributes() -> dict[str, dict[str, str]]:
    """Give every kept `_QC` the unit `1` and a description written here.

    A judgement: the archive's variable list mislabels some `_QC` columns as
    their parent variable, so neither its unit nor its definition is used.
    `checked_flags` checks the values are the 0-1 fractions this describes.
    """
    return {
        f"{base}_QC": {"units": "1", "description": QC_DESCRIPTION.format(base)}
        for base in QC
    }


@tag(action="interprets")
def cell_methods() -> dict[str, str]:
    """Say which variables are daily means of their half-hourly values.

    A judgement, checked against the half-hourly file at UK-Cvn and ES-Dnn
    rather than taken from the archive's definitions: every variable in
    `SCALARS` and `PROFILES` is the mean of the day's half-hours, apart from
    those in `NOT_MEANS`. The uncertainties are not means, and `LE_CORR` and
    `H_CORR`, though defined as "average from half-hourly data", differ from
    the mean of half-hourly values by up to 51 W m-2 at UK-Cvn.
    """
    return {
        name: "time: mean" for name in [*SCALARS, *PROFILES] if name not in NOT_MEANS
    }


@tag(action="annotates")
def variable_attributes(
    checked_units: dict[Path, dict[str, str]],
    descriptions: dict[str, dict[str, str]],
    flag_attributes: dict[str, dict[str, str]],
    cell_methods: dict[str, str],
) -> dict[str, dict[str, str]]:
    """Collect each variable's attributes: CF `units`, and the interpretations.

    `units` is the CF unit `checked_units` confirmed for the variable, or for a
    soil profile its sensors; a variable no archive has gets the one in
    `SCALARS`.
    """
    confirmed = {}
    for units in checked_units.values():
        for column, unit in units.items():
            confirmed.setdefault(column, unit)
    result = {}
    for name in [*SCALARS, *PROFILES]:
        attrs = {"units": confirmed.get(name) or {**SCALARS, **PROFILES}[name]}
        attrs.update(descriptions.get(name, {}))
        if name in cell_methods:
            attrs["cell_methods"] = cell_methods[name]
        result[name] = attrs
    result.update(flag_attributes)
    return result


@tag(action="annotates")
def annotated(
    combined: xr.Dataset, variable_attributes: dict[str, dict[str, str]]
) -> xr.Dataset:
    """Set each variable's attributes."""
    ds = combined.copy()
    for name in ds.data_vars:
        ds[name].attrs = dict(variable_attributes[str(name)])
    return ds


@tag(action="annotates")
def bounded(annotated: xr.Dataset) -> xr.Dataset:
    """Add `time_bounds`, the local day each value covers, in UTC.

    `time` is the start of the day, so the bounds are `time` and a day later.
    `time` and its bounds share one encoding, as CF requires.
    """
    start = annotated.time.values
    ds = annotated.assign_coords(
        time_bounds=(("time", "nv"), np.stack([start, start + _DAY], axis=-1))
    )
    ds.time.encoding["units"] = "minutes since 1970-01-01 00:00:00"
    ds.time.attrs.update(
        standard_name="time",
        long_name="time (UTC) at the start of the site's local standard day",
        bounds="time_bounds",
    )
    return ds


@tag(action="annotates")
def global_attributes(
    retrievals: dict[Path, Retrieval],
    checked_sites: dict[Path, Site],
    licences: dict[Path, str],
) -> dict[str, str]:
    """Collect the provenance attributes, and every site's citation.

    `history` has a line per download, from the sidecars, and one for this
    standardisation; `references` has each archive's citation, as the portal
    gives it, since the licence requires one per site.
    """
    history = sorted(history_line(r) for r in retrievals.values())
    history.append(f"{utc_now()} standardised (xharvest {__version__})")
    citations = sorted({r.metadata.get("citation", "") for r in retrievals.values()})
    sites = checked_sites.values()
    versions = ", ".join(sorted({s.oneflux_version for s in sites}))
    return {
        "title": TITLE,
        "institution": "; ".join(
            sorted(
                {
                    f"{s.network} network, processed by {s.processing_center}"
                    for s in sites
                }
            )
        ),
        "source": f"FLUXNET data product (ONEFlux {versions}), ICOS Carbon Portal, "
        f"{DATA_URL}",
        "license": "; ".join(sorted(set(licences.values()))),
        "references": "\n".join(c for c in citations if c),
        "history": "\n".join(history),
    }


@tag(action="annotates")
def dataset(bounded: xr.Dataset, global_attributes: dict[str, str]) -> xr.Dataset:
    """Describe the coordinates, and set the global attributes."""
    ds = bounded.copy()
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
    ds.attrs = dict(global_attributes)
    return ds
