"""Convert COSMOS-UK CoverageJSON into a standardised xarray Dataset.

The result has dims `(time, site)`, with `site_name`, `lat`, `lon` and
`altitude` coordinates per site, and one variable per API parameter. Each
variable keeps the API's units in a CF `units` attribute, and missing values
become NaN; nothing else about the values changes. `time_bounds` records the
period each value covers: a daily value stamped `2025-01-01T00:00` covers that
GMT day, while a 30-minute value covers the 30 minutes *ending* at its stamp.

Examples:
    >>> from pathlib import Path
    >>> from xharvest.cosmos import to_netcdf
    >>> to_netcdf(Path("data/cosmos").glob("*_1D_*.json"),
    ...           "data/cosmos_1D.nc")  # doctest: +SKIP
"""

import json
import re
from collections.abc import Iterable
from datetime import timedelta
from os import PathLike
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from .. import __version__
from ..errors import ProviderError
from ..provenance import history_line, is_sidecar, read_sidecar, utc_now
from ._fetch import API_URL, COLLECTIONS, PERIODS, Collection

INSTITUTION = "UK Centre for Ecology & Hydrology"

_CELL_METHODS = {
    "mean": "mean",
    "sum": "sum",
    "max": "maximum",
    "min": "minimum",
    "instantaneous": "point",
}

_DURATION = re.compile(
    r"^(?P<sign>-)?P(?:(?P<D>\d+)D)?(?:T(?:(?P<H>\d+)H)?(?:(?P<M>\d+)M)?(?:(?P<S>\d+)S)?)?$"
)


def _duration(period: str) -> timedelta:
    """Parse the ISO 8601 durations the API uses, e.g. `PT1D` or `-PT30M`.

    The API writes one day as `PT1D`, with a stray `T`, so a `D` component
    is accepted on either side of it.
    """
    match = _DURATION.match(period.replace("PT1D", "P1D"))
    if match is None or not any(match[k] for k in "DHMS"):
        raise ProviderError(f"cannot read the COSMOS-UK period {period!r}")
    parts = {k: int(match[k] or 0) for k in "DHMS"}
    delta = timedelta(
        days=parts["D"], hours=parts["H"], minutes=parts["M"], seconds=parts["S"]
    )
    return -delta if match["sign"] else delta


def _cell_methods(parameter: dict[str, Any], axis_period: timedelta) -> str:
    method = parameter["measurementType"]["method"]
    if method not in _CELL_METHODS:
        raise ProviderError(f"unknown COSMOS-UK aggregation method {method!r}")
    cell_methods = f"time: {_CELL_METHODS[method]}"
    period = parameter["measurementType"]["period"]
    if method != "instantaneous" and abs(_duration(period)) != axis_period:
        cell_methods += f" (comment: over {period.lstrip('-')} within each period)"
    return cell_methods


def _variable_attrs(name: str, parameter: dict[str, Any], axis_period: timedelta):
    try:
        units = parameter["unit"]["symbol"]["value"]
    except KeyError:
        raise ProviderError(f"COSMOS-UK parameter {name!r} has no units") from None
    return {
        "units": units,
        "long_name": parameter["label"],
        "description": parameter["description"],
        "cell_methods": _cell_methods(parameter, axis_period),
    }


def _site_dataset(
    coverage: dict[str, Any],
    parameters: dict[str, Any],
    axis_period: timedelta,
    site_names: dict[str, str],
) -> xr.Dataset:
    axes = coverage["domain"]["axes"]
    time = np.array([t.rstrip("Z") for t in axes["t"]["values"]], "datetime64[ns]")
    data_vars = {}
    for name, values in coverage["ranges"].items():
        array = np.array(
            [np.nan if v is None else v for v in values["values"]], dtype=float
        )
        data_vars[name] = (
            ("time", "site"),
            array[:, None],
            _variable_attrs(name, parameters[name], axis_period),
        )
    return xr.Dataset(
        data_vars,
        coords={
            "time": time,
            "site": [coverage["dct:identifier"]],
            "site_name": ("site", [site_names[coverage["dct:identifier"]]]),
            "lat": ("site", axes["y"]["values"][:1]),
            "lon": ("site", axes["x"]["values"][:1]),
            "altitude": ("site", axes["z"]["values"][:1]),
        },
    )


def _collection(path: Path, metadata: dict[str, Any]) -> Collection:
    collection = metadata.get("collection")
    if collection not in COLLECTIONS:
        raise ValueError(
            f"the sidecar for {path} does not name a COSMOS-UK collection; "
            "fetch it again with overwrite=True"
        )
    return collection


def _read(path: Path) -> dict[str, Any]:
    try:
        body = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderError(f"{path} is not a COSMOS-UK JSON response") from None
    if (
        not isinstance(body, dict)
        or body.get("domainType") != "PointSeries"
        or "coverages" not in body
    ):
        raise ProviderError(f"{path} is not a COSMOS-UK point-series response")
    return body


def standardise(paths: Iterable[str | PathLike]) -> xr.Dataset:
    """Combine raw COSMOS-UK files into one standardised Dataset.

    Args:
        paths: CoverageJSON files written by `xharvest.cosmos.fetch`, all from
            the same collection. Provenance sidecars among them are skipped, so a
            glob over the download directory works.

    Returns:
        A Dataset with dims `(time, site)`. Sites are outer-joined on time, so a
        site with a shorter record is NaN-padded.

    Raises:
        ValueError: If no files are given, they mix collections, or a sidecar
            lacks the collection or a site name.
        FileNotFoundError: If a file has no provenance sidecar.
        ProviderError: If a file is not a COSMOS-UK response the connector can read.
    """
    paths = sorted(Path(p) for p in paths if not is_sidecar(p))
    if not paths:
        raise ValueError("no COSMOS-UK files to standardise")

    sites, retrievals, licences, collections = [], [], set(), set()
    for path in paths:
        body = _read(path)
        retrieval = read_sidecar(path)
        retrievals.append(retrieval)
        licences.add(body["dct:license"])
        collection = _collection(path, retrieval.metadata)
        collections.add(collection)
        axis_period = PERIODS[collection].length
        site_names = retrieval.metadata.get("site_names", {})
        for coverage in body["coverages"]:
            if coverage["dct:identifier"] not in site_names:
                raise ValueError(
                    f"the sidecar for {path} has no name for site "
                    f"{coverage['dct:identifier']}; fetch it again with overwrite=True"
                )
            sites.append(
                _site_dataset(coverage, body["parameters"], axis_period, site_names)
            )
    if len(collections) > 1:
        raise ValueError(
            f"files mix COSMOS-UK collections ({', '.join(sorted(collections))}); "
            "standardise one collection at a time"
        )

    ds = xr.concat(sites, dim="site", join="outer", combine_attrs="override")
    ds = ds.sortby("time")

    period = PERIODS[collections.pop()]
    step = np.timedelta64(period.length)
    if period.stamp_ends:
        bounds = [ds.time.values - step, ds.time.values]
    else:
        bounds = [ds.time.values, ds.time.values + step]
    ds = ds.assign_coords(time_bounds=(("time", "nv"), np.stack(bounds, axis=-1)))
    # One encoding for both, so time and its bounds share units as CF requires.
    ds.time.encoding["units"] = "minutes since 1970-01-01 00:00:00"
    ds.time.attrs.update(
        standard_name="time",
        long_name="time (UTC)",
        bounds="time_bounds",
    )
    ds.site.attrs.update(long_name="COSMOS-UK site identifier", cf_role="timeseries_id")
    ds.site_name.attrs.update(long_name="COSMOS-UK site name")
    ds.lat.attrs.update(standard_name="latitude", units="degrees_north")
    ds.lon.attrs.update(standard_name="longitude", units="degrees_east")
    ds.altitude.attrs.update(
        standard_name="height_above_mean_sea_level",
        units="m",
        comment="z coordinate of the API response, in vertical CRS EPSG:5703",
    )

    history = sorted(history_line(r) for r in retrievals)
    history.append(f"{utc_now()} standardised (xharvest {__version__})")
    ds.attrs = {
        "title": "COSMOS-UK site data",
        "featureType": "timeSeries",
        "institution": INSTITUTION,
        "source": f"COSMOS-UK API, {API_URL}",
        "license": "; ".join(sorted(licences)),
        "history": "\n".join(history),
    }
    return ds


def to_netcdf(paths: Iterable[str | PathLike], out: str | PathLike) -> Path:
    """Standardise raw COSMOS-UK files and write the result to netCDF.

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
