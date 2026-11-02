"""Download COSMOS-UK site data from the COSMOS-UK API.

The API (https://cosmos-api.ceh.ac.uk) is an OGC EDR service that needs no
credentials. `fetch` writes one CoverageJSON file per site, each with a provenance
sidecar, and skips files already present.

Examples:
    >>> from datetime import date
    >>> from xharvest.cosmos import fetch
    >>> paths = fetch(["ALIC1", "BUNNY"], date(2025, 1, 1), date(2025, 1, 31),
    ...               "data/cosmos")  # doctest: +SKIP
"""

import json
from collections.abc import Iterable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from .._extras import require
from ..errors import ProviderError
from ..provenance import is_fetched, save

if TYPE_CHECKING:
    import httpx

API_URL = "https://cosmos-api.ceh.ac.uk"

Collection = Literal["1D", "30M"]
"""The API's collections: daily, and 30-minute."""


@dataclass(frozen=True)
class _Period:
    length: timedelta
    # Whether a stamp marks the end of its period rather than the start.
    stamp_ends: bool


# Settled by summing 30-minute values into daily ones; see the provider page.
PERIODS: dict[Collection, _Period] = {
    "1D": _Period(timedelta(days=1), stamp_ends=False),
    "30M": _Period(timedelta(minutes=30), stamp_ends=True),
}
COLLECTIONS: tuple[Collection, ...] = tuple(PERIODS)

_TIMEOUT = 120.0


@dataclass(frozen=True)
class Site:
    """A COSMOS-UK site.

    Attributes:
        id: The site identifier, e.g. `"ALIC1"`.
        name: The site name, e.g. `"Alice Holt"`.
        lat: Latitude, in degrees north (WGS 84).
        lon: Longitude, in degrees east (WGS 84).
        period: The period with data, as an ISO 8601 interval.
    """

    id: str
    name: str
    lat: float
    lon: float
    period: str


def _client(
    client: "httpx.Client | None",
) -> "AbstractContextManager[httpx.Client]":
    # A caller's client is left open; one created here is closed after use.
    if client is not None:
        return nullcontext(client)
    httpx = require("httpx", "cosmos")
    return httpx.Client(timeout=_TIMEOUT)


def _check_collection(collection: str) -> None:
    if collection not in COLLECTIONS:
        raise ValueError(
            f"unknown COSMOS-UK collection {collection!r}; "
            f"expected one of {', '.join(COLLECTIONS)}"
        )


def _get(client: "httpx.Client", url: str, params: dict[str, Any]) -> bytes:
    response = client.get(url, params=params)
    if response.is_success:
        return response.content
    try:
        detail = response.json()["description"]
    except (ValueError, KeyError, TypeError):
        detail = response.text[:500]
    raise ProviderError(f"COSMOS-UK API returned {response.status_code}: {detail}")


def _lat_lon(coordinates: list[float]) -> tuple[float, float]:
    # The /locations GeoJSON lists [lat, lon], against the GeoJSON spec's
    # [lon, lat]. UK latitudes (49-61) and longitudes (-9-2) cannot overlap, so
    # this reads either order correctly if the API is ever fixed.
    a, b = coordinates[:2]
    return (a, b) if a > b else (b, a)


def sites(
    collection: Collection = "1D", *, client: "httpx.Client | None" = None
) -> list[Site]:
    """List the sites with data in `collection`.

    Args:
        collection: `"1D"` for daily data, `"30M"` for 30-minute data.
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The sites, in the order the API lists them.

    Raises:
        ProviderError: If the API returns an error.
    """
    _check_collection(collection)
    with _client(client) as http:
        body = _get(http, f"{API_URL}/collections/{collection}/locations", {})
    features = json.loads(body)["features"]
    result = []
    for feature in features:
        lat, lon = _lat_lon(feature["geometry"]["coordinates"])
        props = feature["properties"]
        result.append(
            Site(
                id=feature["id"],
                name=props["label"],
                lat=lat,
                lon=lon,
                period=props["datetime"],
            )
        )
    return result


def _timestamp(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _query_time(value: date | datetime, collection: Collection, *, end: bool) -> str:
    """The stamp to request for a bound; a date selects the whole day."""
    if isinstance(value, datetime):
        return _timestamp(value)
    # The first or last stamp whose period lies within the day.
    midnight = datetime(value.year, value.month, value.day)
    period = PERIODS[collection]
    if not end:
        first = midnight + period.length if period.stamp_ends else midnight
        return _timestamp(first)
    next_midnight = midnight + timedelta(days=1)
    last = next_midnight if period.stamp_ends else next_midnight - period.length
    return _timestamp(last)


def _file_stamp(value: date | datetime) -> str:
    # Dates name a file by day; datetimes keep the time, so requests that differ
    # only in time of day do not share a file.
    if isinstance(value, datetime):
        return _timestamp(value)[:19].replace("-", "").replace(":", "")
    return value.strftime("%Y%m%d")


def fetch(
    site_ids: str | Iterable[str],
    start: date | datetime,
    end: date | datetime,
    out: str | PathLike,
    *,
    parameters: Iterable[str] | None = None,
    collection: Collection = "1D",
    overwrite: bool = False,
    client: "httpx.Client | None" = None,
) -> list[Path]:
    """Download data for one or more sites, one CoverageJSON file per site.

    Each file is named `{site}_{collection}_{start}_{end}.json`, where a date is
    written `%Y%m%d` and a datetime `%Y%m%dT%H%M%S` in UTC. It has a provenance
    sidecar next to it (see `xharvest.provenance`), which also records the
    collection and the site's name, since the data response omits both. Pass
    the returned paths to `xharvest.cosmos.standardise`.

    Args:
        site_ids: Site identifiers, e.g. `"ALIC1"` or `["ALIC1", "BUNNY"]`.
            `sites` lists them.
        start: First timestamp to include; a naive `datetime` is taken as UTC.
            A `date` includes every value whose period lies within that GMT day,
            which for `30M` starts at the 00:30 stamp.
        end: Last timestamp to include, as for `start`; the interval is closed.
            A `date` includes the whole day, which for `30M` ends at the 00:00
            stamp of the next day.
        out: Directory to write to; created if missing.
        parameters: Parameter names to request, e.g. `["cosmos_vwc", "precip"]`.
            Every parameter is requested if omitted.
        collection: `"1D"` for daily data, `"30M"` for 30-minute data.
        overwrite: Download again even if a file already exists. Without it, a
            file is skipped if its sidecar records the same request, and
            downloaded again if it has no sidecar (an interrupted download).
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The paths of the data files, one per site, in the order given.

    Raises:
        ProviderError: If the API rejects a request, e.g. for an unknown site or
            parameter, or a range outside a site's record. The message is the
            API's own.
        ValueError: If a file exists from a different request, e.g. with other
            parameters, and `overwrite` is not set.
    """
    _check_collection(collection)
    site_ids = [site_ids] if isinstance(site_ids, str) else list(site_ids)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    first = _query_time(start, collection, end=False)
    last = _query_time(end, collection, end=True)
    params: dict[str, Any] = {"datetime": f"{first}/{last}"}
    if parameters is not None:
        params["parameter-name"] = ",".join(parameters)

    stamp = f"{_file_stamp(start)}_{_file_stamp(end)}"
    url = f"{API_URL}/collections/{collection}/locations"
    paths = [out / f"{site_id}_{collection}_{stamp}.json" for site_id in site_ids]
    todo = [
        (site_id, path)
        for site_id, path in zip(site_ids, paths, strict=True)
        if overwrite or not is_fetched(path, f"{url}/{site_id}", params)
    ]
    if not todo:
        return paths
    with _client(client) as http:
        # Data responses carry no site names, so look them up once.
        names = {s.id: s.name for s in sites(collection, client=http)}
        for site_id, path in todo:
            content = _get(http, f"{url}/{site_id}", params)
            metadata = {
                "collection": collection,
                "site_names": {site_id: names.get(site_id, "")},
            }
            save(path, content, f"{url}/{site_id}", params, metadata)
    return paths
