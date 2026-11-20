"""Nodes that standardise COSMOS-UK CoverageJSON into one Dataset.

`standardise` builds its graph from these and computes `dataset` from `paths`.
Every node acts on all the files at once. A file holds a coverage per site, and
the nodes that act on coverages take and return a mapping from `(path, site)`,
a `Piece`, to that coverage's part.
"""

import json
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from hamilton.function_modifiers import tag

from .. import __version__
from ..errors import ProviderError
from ..provenance import Retrieval, history_line, is_sidecar, read_sidecar, utc_now
from ._fetch import API_URL, COLLECTIONS, PERIODS, Collection, Period

type Piece = tuple[Path, str]
"""A file and the identifier of one site it covers."""

INSTITUTION = "UK Centre for Ecology & Hydrology"

TITLE = "COSMOS-UK site data"

CELL_METHODS = {
    "mean": "mean",
    "sum": "sum",
    "max": "maximum",
    "min": "minimum",
    "instantaneous": "point",
}
"""The CF `cell_methods` method for each aggregation method the API names."""

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


@tag(action="selects")
def file_paths(paths: list[Path]) -> list[Path]:
    """Keep the data files among `paths`, sorted, and drop provenance sidecars.

    So a glob over the download directory works.

    Raises:
        ValueError: If no files remain.
    """
    files = sorted(p for p in paths if not is_sidecar(p))
    if not files:
        raise ValueError("no COSMOS-UK files to standardise")
    return files


@tag(action="reads")
def responses(file_paths: list[Path]) -> dict[Path, dict[str, Any]]:
    """Parse each file as the API's CoverageJSON point-series response.

    Raises:
        ProviderError: If a file is not JSON, or not a point-series response.
    """
    result = {}
    for path in file_paths:
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
        result[path] = body
    return result


@tag(action="reads")
def retrievals(file_paths: list[Path]) -> dict[Path, Retrieval]:
    """Read each file's provenance sidecar, written by `fetch`.

    The sidecar records where and when the file was downloaded, its
    collection, and its sites' names, none of which the response holds.

    Raises:
        FileNotFoundError: If a file has no sidecar.
    """
    return {path: read_sidecar(path) for path in file_paths}


@tag(action="reads")
def collections(retrievals: dict[Path, Retrieval]) -> dict[Path, Collection]:
    """Read the collection each file was fetched from, from its sidecar.

    Raises:
        ValueError: If a sidecar does not name a COSMOS-UK collection.
    """
    result = {}
    for path, retrieval in retrievals.items():
        collection = retrieval.metadata.get("collection")
        if collection not in COLLECTIONS:
            raise ValueError(
                f"the sidecar for {path} does not name a COSMOS-UK collection; "
                "fetch it again with overwrite=True"
            )
        result[path] = collection
    return result


@tag(action="checks")
def collection(collections: dict[Path, Collection]) -> Collection:
    """Check that every file is from one collection, and return it.

    Daily and 30-minute values cannot share a time axis.

    Raises:
        ValueError: If the files mix collections.
    """
    found = set(collections.values())
    if len(found) > 1:
        raise ValueError(
            f"files mix COSMOS-UK collections ({', '.join(sorted(found))}); "
            "standardise one collection at a time"
        )
    return found.pop()


@tag(action="interprets")
def period(collection: Collection) -> Period:
    """The period each value of the collection covers, relative to its stamp.

    A judgement, as the API does not say: a daily value stamped
    `2025-01-01T00:00` covers that GMT day, and a 30-minute value covers the 30
    minutes ending at its stamp. Checked by summing the 30-minute precipitation
    over each day, which matches the daily totals to within rounding only under
    this reading.
    """
    return PERIODS[collection]


@tag(action="reads")
def coverages(responses: dict[Path, dict[str, Any]]) -> dict[Piece, dict[str, Any]]:
    """Take each site's coverage from each file."""
    return {
        (path, coverage["dct:identifier"]): coverage
        for path, body in responses.items()
        for coverage in body["coverages"]
    }


@tag(action="reads")
def site_names(
    coverages: dict[Piece, dict[str, Any]], retrievals: dict[Path, Retrieval]
) -> dict[str, str]:
    """Read each site's name from the sidecar of a file that covers it.

    The response identifies a site only by its code, so `fetch` records the
    names the API's site list gives.

    Raises:
        ValueError: If a file's sidecar has no name for a site it covers.
    """
    result = {}
    for path, site in coverages:
        names = retrievals[path].metadata.get("site_names", {})
        if site not in names:
            raise ValueError(
                f"the sidecar for {path} has no name for site {site}; "
                "fetch it again with overwrite=True"
            )
        result.setdefault(site, names[site])
    return result


@tag(action="reads")
def locations(coverages: dict[Piece, dict[str, Any]]) -> dict[Piece, dict[str, float]]:
    """Read each coverage's position: its `y`, `x` and `z` as lat, lon and altitude.

    A point series has one position, so each axis holds one value.
    """
    result = {}
    for piece, coverage in coverages.items():
        axes = coverage["domain"]["axes"]
        result[piece] = {
            "lat": axes["y"]["values"][0],
            "lon": axes["x"]["values"][0],
            "altitude": axes["z"]["values"][0],
        }
    return result


@tag(action="decodes")
def times(coverages: dict[Piece, dict[str, Any]]) -> dict[Piece, np.ndarray]:
    """Decode each coverage's timestamps to naive `datetime64` in UTC.

    The API writes them in UTC, with a `Z`.
    """
    return {
        piece: np.array(
            [t.rstrip("Z") for t in coverage["domain"]["axes"]["t"]["values"]],
            "datetime64[ns]",
        )
        for piece, coverage in coverages.items()
    }


@tag(action="decodes")
def values(
    coverages: dict[Piece, dict[str, Any]],
) -> dict[Piece, dict[str, np.ndarray]]:
    """Decode each coverage's values to floats, with `null` as NaN.

    Integer parameters, such as `snow`, become floats too, so they can hold NaN.
    """
    return {
        piece: {
            name: np.array(
                [np.nan if v is None else v for v in series["values"]], dtype=float
            )
            for name, series in coverage["ranges"].items()
        }
        for piece, coverage in coverages.items()
    }


@tag(action="reads")
def parameters(responses: dict[Path, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Read each parameter's metadata, from the first file, in path order, with it.

    Every response from one collection describes a parameter the same way.
    """
    result: dict[str, dict[str, Any]] = {}
    for body in responses.values():
        for name, parameter in body["parameters"].items():
            result.setdefault(name, parameter)
    return result


@tag(action="reads")
def licences(responses: dict[Path, dict[str, Any]]) -> set[str]:
    """Read the licence each response states."""
    return {body["dct:license"] for body in responses.values()}


@tag(action="reshapes")
def site_datasets(
    times: dict[Piece, np.ndarray],
    values: dict[Piece, dict[str, np.ndarray]],
    locations: dict[Piece, dict[str, float]],
    site_names: dict[str, str],
) -> dict[Piece, xr.Dataset]:
    """Arrange each coverage into a Dataset with one site, on `(time, site)`."""
    result = {}
    for piece, arrays in values.items():
        site = piece[1]
        location = locations[piece]
        result[piece] = xr.Dataset(
            {
                name: (("time", "site"), array[:, None])
                for name, array in arrays.items()
            },
            coords={
                "time": times[piece],
                "site": [site],
                "site_name": ("site", [site_names[site]]),
                "lat": ("site", [location["lat"]]),
                "lon": ("site", [location["lon"]]),
                "altitude": ("site", [location["altitude"]]),
            },
        )
    return result


@tag(action="reshapes")
def site_records(site_datasets: dict[Piece, xr.Dataset]) -> list[xr.Dataset]:
    """Join each site's files into one record, a site per Dataset.

    Files of one site covering different periods are outer-joined on time, so a
    gap between them stays a gap.

    Raises:
        ValueError: If two files of one site disagree where both have a value,
            as they do when the provider revised its data between downloads.
    """
    pieces: dict[str, list[xr.Dataset]] = defaultdict(list)
    for (_, site), ds in site_datasets.items():
        pieces[site].append(ds)
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
                f"files for site {site} disagree where they overlap, so the provider "
                "revised its data between the downloads; remove the older file, or "
                f"fetch the overlap again with overwrite=True ({err})"
            ) from None
    return records


@tag(action="reshapes")
def combined(site_records: list[xr.Dataset]) -> xr.Dataset:
    """Join the sites on `time`, padding each with NaN.

    A site with a shorter record, or without a parameter another site has, is
    NaN where it has no value, so every site has the same variables and times.
    """
    ds = xr.concat(site_records, dim="site", join="outer", combine_attrs="override")
    return ds.sortby("time")


@tag(action="annotates")
def cell_methods(
    parameters: dict[str, dict[str, Any]], period: Period
) -> dict[str, str]:
    """Write each parameter's aggregation as CF `cell_methods`.

    The API gives a method and the period it covers. Where an aggregate covers
    less than the collection's period, such as albedo averaged over four hours
    of each day, a comment says so.

    Raises:
        ProviderError: If a parameter has a method not in `CELL_METHODS`, or a
            period that cannot be read.
    """
    result = {}
    for name, parameter in parameters.items():
        method = parameter["measurementType"]["method"]
        if method not in CELL_METHODS:
            raise ProviderError(f"unknown COSMOS-UK aggregation method {method!r}")
        text = f"time: {CELL_METHODS[method]}"
        covers = parameter["measurementType"]["period"]
        if method != "instantaneous" and abs(_duration(covers)) != period.length:
            text += f" (comment: over {covers.lstrip('-')} within each period)"
        result[name] = text
    return result


@tag(action="annotates")
def variable_attributes(
    parameters: dict[str, dict[str, Any]], cell_methods: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Collect each variable's attributes from the API's parameter metadata.

    `units` is the API's unit symbol, as given: it is already CF.

    Raises:
        ProviderError: If a parameter has no unit.
    """
    result = {}
    for name, parameter in parameters.items():
        try:
            units = parameter["unit"]["symbol"]["value"]
        except KeyError:
            raise ProviderError(f"COSMOS-UK parameter {name!r} has no units") from None
        result[name] = {
            "units": units,
            "long_name": parameter["label"],
            "description": parameter["description"],
            "cell_methods": cell_methods[name],
        }
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
def bounded(annotated: xr.Dataset, period: Period) -> xr.Dataset:
    """Add `time_bounds`, the period each value covers, from `period`.

    `time` and its bounds share one encoding, as CF requires.
    """
    stamps = annotated.time.values
    step = np.timedelta64(period.length)
    bounds = [stamps - step, stamps] if period.stamp_ends else [stamps, stamps + step]
    ds = annotated.assign_coords(time_bounds=(("time", "nv"), np.stack(bounds, -1)))
    ds.time.encoding["units"] = "minutes since 1970-01-01 00:00:00"
    ds.time.attrs.update(
        standard_name="time", long_name="time (UTC)", bounds="time_bounds"
    )
    return ds


@tag(action="annotates")
def global_attributes(
    retrievals: dict[Path, Retrieval], licences: set[str]
) -> dict[str, str]:
    """Collect the provenance attributes.

    `history` has a line per download, from the sidecars, and one for this
    standardisation.
    """
    history = sorted(history_line(r) for r in retrievals.values())
    history.append(f"{utc_now()} standardised (xharvest {__version__})")
    return {
        "title": TITLE,
        "featureType": "timeSeries",
        "institution": INSTITUTION,
        "source": f"COSMOS-UK API, {API_URL}",
        "license": "; ".join(sorted(licences)),
        "history": "\n".join(history),
    }


@tag(action="annotates")
def dataset(bounded: xr.Dataset, global_attributes: dict[str, str]) -> xr.Dataset:
    """Describe the coordinates, and set the global attributes."""
    ds = bounded.copy()
    ds.site.attrs.update(long_name="COSMOS-UK site identifier", cf_role="timeseries_id")
    ds.site_name.attrs.update(long_name="COSMOS-UK site name")
    ds.lat.attrs.update(standard_name="latitude", units="degrees_north")
    ds.lon.attrs.update(standard_name="longitude", units="degrees_east")
    ds.altitude.attrs.update(
        standard_name="height_above_mean_sea_level",
        units="m",
        comment="z coordinate of the API response, in vertical CRS EPSG:5703",
    )
    ds.attrs = dict(global_attributes)
    return ds
