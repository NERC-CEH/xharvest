"""Download ICOS ecosystem stations' ETC L2 archives from the ICOS Carbon Portal.

The ETC L2 archive (`etcArchiveProduct`) is the most complete data collection for
an ICOS ecosystem station: its fluxes, meteorology and FLUXNET files, and the
ancillary measurements, such as LAI, biomass and soil properties, that
`xharvest.icos.standardise` reads. There is one current archive per station; an
interim archive, updated monthly, supersedes the station's final one. Discovery
and download need no credentials, as for `xharvest.fluxnet`, whose portal
plumbing this shares.

Examples:
    >>> from xharvest.icos import fetch
    >>> paths = fetch(["UK-AMo", "GL-ZaH"], "data/raw")  # doctest: +SKIP
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING

from ..errors import ProviderError
from ..fluxnet._fetch import (
    DATA_URL,
    HANDLE_URL,
    SPARQL_URL,
    download,
    portal_client,
    portal_request,
)
from ..provenance import is_fetched, save

if TYPE_CHECKING:
    import httpx

PRODUCT = "http://meta.icos-cp.eu/resources/cpmeta/etcArchiveProduct"

# Superseded versions stay in the portal, so keep only objects nothing replaces.
STATIONS_QUERY = f"""\
prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
prefix prov: <http://www.w3.org/ns/prov#>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix skos: <http://www.w3.org/2004/02/skos/core#>
prefix dcterms: <http://purl.org/dc/terms/>
select ?dobj ?fileName ?sha256 ?stationId ?stationName ?lat ?lon ?timeStart
    ?timeEnd ?citation ?licenceName ?licence
where {{
    ?dobj cpmeta:hasObjectSpec <{PRODUCT}> .
    FILTER NOT EXISTS {{ [] cpmeta:isNextVersionOf ?dobj }}
    ?dobj cpmeta:hasName ?fileName ;
        cpmeta:hasSha256sum ?sha256 ;
        cpmeta:wasAcquiredBy/prov:wasAssociatedWith ?station .
    ?dobj cpmeta:hasStartTime | (cpmeta:wasAcquiredBy/prov:startedAtTime) ?timeStart .
    ?dobj cpmeta:hasEndTime | (cpmeta:wasAcquiredBy/prov:endedAtTime) ?timeEnd .
    ?station cpmeta:hasStationId ?stationId .
    OPTIONAL {{ ?station cpmeta:hasName ?stationName }}
    OPTIONAL {{ ?station cpmeta:hasLatitude ?lat ; cpmeta:hasLongitude ?lon }}
    OPTIONAL {{ ?dobj cpmeta:hasCitationString ?citation }}
    OPTIONAL {{
        ?dobj dcterms:license ?lic .
        OPTIONAL {{ ?lic rdfs:label ?licenceName }}
        OPTIONAL {{ ?lic skos:exactMatch ?licence }}
    }}
}}
order by ?stationId
"""


@dataclass(frozen=True)
class Station:
    """An ICOS ecosystem station with an ETC L2 archive on the portal.

    Attributes:
        id: The station code, e.g. `"UK-AMo"`.
        name: The station name, e.g. `"Auchencorth Moss"`.
        lat: Latitude, in degrees north, if the portal gives one.
        lon: Longitude, in degrees east, if the portal gives one.
        start: Start of the archive's record, in UTC.
        end: End of the archive's record, in UTC.
        file_name: The archive's file name, e.g.
            `"ICOSETC_UK-AMo_ARCHIVE_INTERIM_L2.zip"`.
        object_uri: The portal's landing page for the archive.
        sha256: The archive's SHA-256, as unpadded standard base64.
        citation: How to cite the archive, as the portal gives it.
        licence: The archive's licence, as its name and the licence it
            matches, e.g. `"ICOS CCBY4 Data Licence
            (https://creativecommons.org/licenses/by/4.0)"`.
    """

    id: str
    name: str
    lat: float | None
    lon: float | None
    start: datetime
    end: datetime
    file_name: str
    object_uri: str
    sha256: str
    citation: str
    licence: str

    @property
    def object_id(self) -> str:
        """The portal's identifier for the archive, the last part of `object_uri`."""
        return self.object_uri.rsplit("/", 1)[-1]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _station(binding: dict[str, dict[str, str]]) -> Station:
    def value(key: str) -> str | None:
        return binding[key]["value"] if key in binding else None

    lat, lon = value("lat"), value("lon")
    name, match = value("licenceName"), value("licence")
    licence = " ".join(filter(None, [name, match and f"({match})"]))
    return Station(
        id=binding["stationId"]["value"],
        name=value("stationName") or "",
        lat=None if lat is None else float(lat),
        lon=None if lon is None else float(lon),
        start=_time(binding["timeStart"]["value"]),
        end=_time(binding["timeEnd"]["value"]),
        file_name=binding["fileName"]["value"],
        object_uri=binding["dobj"]["value"],
        sha256=binding["sha256"]["value"],
        citation=value("citation") or "",
        licence=licence,
    )


def stations(*, client: "httpx.Client | None" = None) -> list[Station]:
    """List the ICOS ecosystem stations with a current ETC L2 archive.

    A station usually has one current archive, but can have both a final and an
    interim one, which nothing marks as superseding the other. The one whose
    record ends later is listed, as the more complete; on a tie, the final one.
    Not every station's archive holds ancillary measurements: about one in ten
    has none.

    Args:
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The stations, ordered by station code.

    Raises:
        ProviderError: If the portal cannot be reached or returns an error.
    """
    with portal_client(client, "icos") as http:
        body = portal_request(
            http,
            "POST",
            SPARQL_URL,
            data={"query": STATIONS_QUERY},
            headers={"Accept": "application/sparql-results+json"},
        )
    try:
        bindings = json.loads(body)["results"]["bindings"]
        found = [_station(b) for b in bindings]
    except (ValueError, KeyError, TypeError) as err:
        raise ProviderError(
            f"cannot read the ICOS Carbon Portal's station list: {err!r}"
        ) from None
    latest: dict[str, Station] = {}
    for station in found:
        kept = latest.get(station.id)
        if kept is None or _recency(station) > _recency(kept):
            latest[station.id] = station
    return sorted(latest.values(), key=lambda s: s.id)


def _recency(station: Station) -> tuple[datetime, bool]:
    # Later end first; on a tie, the final archive over the interim one.
    return station.end, "_INTERIM_" not in station.file_name


def fetch(
    station_ids: str | Iterable[str],
    out: str | PathLike,
    *,
    overwrite: bool = False,
    client: "httpx.Client | None" = None,
) -> list[Path]:
    """Download the current ETC L2 archive of one or more stations.

    Each archive holds the station's whole record, 5-330 MB, so there is no date
    range. Files keep the portal's name, e.g.
    `ICOSETC_UK-AMo_ARCHIVE_INTERIM_L2.zip`, which does not change between
    monthly versions: once the portal has a newer one, fetching raises until
    `overwrite` is passed, rather than replacing the old one unasked.
    Each has a provenance sidecar next to it (see `xharvest.provenance`), which
    also records the archive's citation and licence. Pass the returned paths to
    `xharvest.icos.standardise`.

    Args:
        station_ids: Station codes, e.g. `"UK-AMo"` or `["UK-AMo", "GL-ZaH"]`.
            `stations` lists them.
        out: Directory to write to; created if missing.
        overwrite: Download again even if a file already exists. Without it, a
            file is skipped if its sidecar records the same archive, and
            downloaded again if it has no sidecar (an interrupted download).
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The paths of the archives, one per station, in the order given.

    Raises:
        ProviderError: If the portal cannot be reached or returns an error, or a
            download does not match the SHA-256 the portal publishes.
        ValueError: If a station has no archive on the portal, or a file exists
            from a different request and `overwrite` is not set.
    """
    station_ids = [station_ids] if isinstance(station_ids, str) else list(station_ids)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with portal_client(client, "icos") as http:
        available = {s.id: s for s in stations(client=http)}
        missing = [s for s in station_ids if s not in available]
        if missing:
            raise ValueError(
                f"no ETC L2 archive on the ICOS Carbon Portal for "
                f"{', '.join(missing)}; `stations()` lists those with one"
            )
        paths = []
        for station_id in station_ids:
            station = available[station_id]
            path = out / station.file_name
            url = f"{DATA_URL}/objects/{station.object_id}"
            paths.append(path)
            if not overwrite and is_fetched(path, url, {}):
                continue
            content = download(http, station.object_uri, station.sha256, station_id)
            metadata = {
                "station_id": station.id,
                "station_name": station.name,
                "object": station.object_uri,
                "pid": f"{HANDLE_URL}/{station.object_id}",
                "sha256": station.sha256,
                "citation": station.citation,
                "licence": station.licence,
            }
            save(path, content, url, {}, metadata)
    return paths
