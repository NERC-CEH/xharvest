"""Download FLUXNET archives from the ICOS Carbon Portal.

The portal (https://www.icos-cp.eu) hosts the ONEFlux v1.3 FLUXNET release for
several hundred sites, from ICOS and other networks. Discovery is one SPARQL query
and needs no credentials; so does downloading, which goes through the portal's
licence-acceptance link. `fetch` writes one ZIP archive per site, each with a
provenance sidecar, checks it against the SHA-256 the portal publishes, and skips
archives already present.

Examples:
    >>> from xharvest.fluxnet import fetch
    >>> paths = fetch(["UK-Cvn", "UK-AMo"], "data/raw")  # doctest: +SKIP
"""

import base64
import hashlib
import json
from collections.abc import Iterable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._extras import require
from ..errors import ProviderError
from ..provenance import is_fetched, save

if TYPE_CHECKING:
    import httpx

SPARQL_URL = "https://meta.icos-cp.eu/sparql"
DATA_URL = "https://data.icos-cp.eu"
HANDLE_URL = "https://hdl.handle.net/11676"
PRODUCT = "http://meta.icos-cp.eu/resources/cpmeta/miscFluxnetArchiveProduct"

_TIMEOUT = 120.0

# Superseded versions stay in the portal, so keep only objects nothing replaces.
SITES_QUERY = f"""\
prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
prefix prov: <http://www.w3.org/ns/prov#>
select ?dobj ?fileName ?sha256 ?siteId ?siteName ?lat ?lon ?timeStart ?timeEnd
    ?citation
where {{
    ?dobj cpmeta:hasObjectSpec <{PRODUCT}> .
    FILTER NOT EXISTS {{ [] cpmeta:isNextVersionOf ?dobj }}
    ?dobj cpmeta:hasName ?fileName ;
        cpmeta:hasSha256sum ?sha256 ;
        cpmeta:wasAcquiredBy/prov:wasAssociatedWith ?station .
    ?dobj cpmeta:hasStartTime | (cpmeta:wasAcquiredBy/prov:startedAtTime) ?timeStart .
    ?dobj cpmeta:hasEndTime | (cpmeta:wasAcquiredBy/prov:endedAtTime) ?timeEnd .
    ?station cpmeta:hasStationId ?siteId .
    OPTIONAL {{ ?station cpmeta:hasName ?siteName }}
    OPTIONAL {{ ?station cpmeta:hasLatitude ?lat ; cpmeta:hasLongitude ?lon }}
    OPTIONAL {{ ?dobj cpmeta:hasCitationString ?citation }}
}}
order by ?siteId
"""


@dataclass(frozen=True)
class Site:
    """A site with a FLUXNET archive on the ICOS Carbon Portal.

    Attributes:
        id: The FLUXNET site code, e.g. `"UK-Cvn"`.
        name: The site name, e.g. `"Coveney"`.
        lat: Latitude, in degrees north, if the portal gives one.
        lon: Longitude, in degrees east, if the portal gives one.
        start: Start of the archive's record, in UTC.
        end: End of the archive's record, in UTC.
        file_name: The archive's file name, e.g.
            `"EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip"`; the first part names
            the network that prepared the data.
        object_uri: The portal's landing page for the archive.
        sha256: The archive's SHA-256, as unpadded URL-safe base64.
        citation: How to cite the archive, as the portal gives it.
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

    @property
    def object_id(self) -> str:
        """The portal's identifier for the archive, the last part of `object_uri`."""
        return self.object_uri.rsplit("/", 1)[-1]


def _client(
    client: "httpx.Client | None",
) -> "AbstractContextManager[httpx.Client]":
    # A caller's client is left open; one created here is closed after use.
    if client is not None:
        return nullcontext(client)
    httpx = require("httpx", "fluxnet")
    return httpx.Client(timeout=_TIMEOUT)


def _request(client: "httpx.Client", method: str, url: str, **kwargs: Any) -> bytes:
    httpx = require("httpx", "fluxnet")
    try:
        response = client.request(method, url, follow_redirects=True, **kwargs)
    except httpx.TransportError as err:
        raise ProviderError(f"could not reach the ICOS Carbon Portal: {err!r}") from err
    if response.is_success:
        return response.content
    raise ProviderError(
        f"ICOS Carbon Portal returned {response.status_code} for {url}: "
        f"{response.text[:500]}"
    )


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _site(binding: dict[str, dict[str, str]]) -> Site:
    def value(key: str) -> str | None:
        return binding[key]["value"] if key in binding else None

    lat, lon = value("lat"), value("lon")
    return Site(
        id=binding["siteId"]["value"],
        name=value("siteName") or "",
        lat=None if lat is None else float(lat),
        lon=None if lon is None else float(lon),
        start=_time(binding["timeStart"]["value"]),
        end=_time(binding["timeEnd"]["value"]),
        file_name=binding["fileName"]["value"],
        object_uri=binding["dobj"]["value"],
        sha256=binding["sha256"]["value"],
        citation=value("citation") or "",
    )


def sites(*, client: "httpx.Client | None" = None) -> list[Site]:
    """List the sites with a current FLUXNET archive on the portal.

    Args:
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The sites, ordered by site code.

    Raises:
        ProviderError: If the portal cannot be reached or returns an error.
    """
    with _client(client) as http:
        body = _request(
            http,
            "POST",
            SPARQL_URL,
            data={"query": SITES_QUERY},
            headers={"Accept": "application/sparql-results+json"},
        )
    try:
        bindings = json.loads(body)["results"]["bindings"]
        return [_site(b) for b in bindings]
    except (ValueError, KeyError, TypeError) as err:
        raise ProviderError(
            f"cannot read the ICOS Carbon Portal's site list: {err!r}"
        ) from None


def sha256(content: bytes) -> str:
    """The SHA-256 of `content` in the portal's form: unpadded URL-safe base64."""
    digest = hashlib.sha256(content).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def fetch(
    site_ids: str | Iterable[str],
    out: str | PathLike,
    *,
    overwrite: bool = False,
    client: "httpx.Client | None" = None,
) -> list[Path]:
    """Download the current FLUXNET archive of one or more sites.

    Each archive holds the site's whole record, at every resolution, so there is
    no date range: select one after standardising. Archives are 20-250 MB.
    Files keep the portal's name, which carries the network, years and release,
    e.g. `EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip`, so a new release is a new
    file. Each has a provenance sidecar next to it (see `xharvest.provenance`),
    which also records the archive's citation. Pass the returned paths to
    `xharvest.fluxnet.standardise`.

    Args:
        site_ids: FLUXNET site codes, e.g. `"UK-Cvn"` or `["UK-Cvn", "UK-AMo"]`.
            `sites` lists them.
        out: Directory to write to; created if missing.
        overwrite: Download again even if a file already exists. Without it, a
            file is skipped if its sidecar records the same archive, and
            downloaded again if it has no sidecar (an interrupted download).
        client: An `httpx.Client` to use, e.g. one with a mock transport for
            testing. A new one is created if omitted.

    Returns:
        The paths of the archives, one per site, in the order given.

    Raises:
        ProviderError: If the portal cannot be reached or returns an error, or a
            download does not match the SHA-256 the portal publishes.
        ValueError: If a site has no archive on the portal, or a file exists
            from a different request and `overwrite` is not set.
    """
    site_ids = [site_ids] if isinstance(site_ids, str) else list(site_ids)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with _client(client) as http:
        available = {s.id: s for s in sites(client=http)}
        missing = [s for s in site_ids if s not in available]
        if missing:
            raise ValueError(
                f"no FLUXNET archive on the ICOS Carbon Portal for "
                f"{', '.join(missing)}; `sites()` lists those with one"
            )
        paths = []
        for site_id in site_ids:
            site = available[site_id]
            path = out / site.file_name
            url = f"{DATA_URL}/objects/{site.object_id}"
            paths.append(path)
            if not overwrite and is_fetched(path, url, {}):
                continue
            # The licence link records acceptance in a cookie, then redirects
            # to the object itself.
            content = _request(
                http,
                "GET",
                f"{DATA_URL}/licence_accept",
                params={"ids": json.dumps([site.object_id])},
            )
            if sha256(content) != site.sha256:
                raise ProviderError(
                    f"the archive downloaded for {site_id} does not match the "
                    f"SHA-256 the ICOS Carbon Portal publishes ({site.object_uri})"
                )
            metadata = {
                "site_id": site.id,
                "site_name": site.name,
                "object": site.object_uri,
                "pid": f"{HANDLE_URL}/{site.object_id}",
                "sha256": site.sha256,
                "citation": site.citation,
            }
            save(path, content, url, {}, metadata)
    return paths
