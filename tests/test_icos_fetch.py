from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from xharvest.errors import ProviderError
from xharvest.icos import fetch, sites
from xharvest.icos._fetch import sha256
from xharvest.provenance import read_sidecar, sidecar_path

FIXTURES = Path(__file__).parent / "fixtures" / "icos"
CVN_FILE = "EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip"


def test_sites_reads_the_site_list(icos_portal):
    found = {s.id: s for s in sites(client=icos_portal.client())}
    assert set(found) == {"UK-Ags", "UK-Cvn"}
    cvn = found["UK-Cvn"]
    assert cvn.name == "Coveney"
    assert (cvn.lat, cvn.lon) == pytest.approx((52.43339, 0.162177))
    assert cvn.start == datetime(2023, 1, 1, tzinfo=UTC)
    assert cvn.end == datetime(2025, 1, 1, tzinfo=UTC)
    assert cvn.file_name == CVN_FILE
    assert cvn.object_id == "37X3GrWRM7AEcdIt8WRasg1l"
    assert "Coveney" in cvn.citation


def test_sites_sends_one_sparql_query(icos_portal):
    sites(client=icos_portal.client())
    (request,) = icos_portal.requests
    assert request.method == "POST"
    assert b"miscFluxnetArchiveProduct" in request.content
    assert request.headers["accept"] == "application/sparql-results+json"


def test_fetch_writes_archive_and_sidecar(icos_portal, tmp_path):
    out = tmp_path / "new" / "dir"
    (path,) = fetch("UK-Cvn", out, client=icos_portal.client())
    assert path == out / CVN_FILE
    assert path.read_bytes() == (FIXTURES / CVN_FILE).read_bytes()
    retrieval = read_sidecar(path)
    assert retrieval.url == "https://data.icos-cp.eu/objects/37X3GrWRM7AEcdIt8WRasg1l"
    assert retrieval.params == {}
    assert retrieval.metadata["site_id"] == "UK-Cvn"
    assert retrieval.metadata["site_name"] == "Coveney"
    assert retrieval.metadata["pid"].endswith("/11676/37X3GrWRM7AEcdIt8WRasg1l")
    assert retrieval.metadata["sha256"] == sha256(path.read_bytes())
    assert "Coveney" in retrieval.metadata["citation"]


def test_fetch_accepts_the_licence_before_downloading(icos_portal, tmp_path):
    fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    accept, download = icos_portal.requests[1:]
    assert accept.url.path == "/licence_accept"
    assert accept.url.params["ids"] == '["37X3GrWRM7AEcdIt8WRasg1l"]'
    assert download.headers["cookie"] == "CpLicenseAcceptedFor=37X3GrWRM7AEcdIt8WRasg1l"


def test_fetch_returns_paths_in_the_order_given(icos_portal, tmp_path):
    paths = fetch(["UK-Cvn", "UK-Ags"], tmp_path, client=icos_portal.client())
    assert [p.name.split("_")[1] for p in paths] == ["UK-Cvn", "UK-Ags"]


def test_fetch_skips_archives_already_fetched(icos_portal, tmp_path):
    fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    assert len(icos_portal.downloads) == 1


def test_fetch_overwrite_downloads_again(icos_portal, tmp_path):
    fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    fetch("UK-Cvn", tmp_path, overwrite=True, client=icos_portal.client())
    assert len(icos_portal.downloads) == 2


def test_fetch_downloads_again_without_a_sidecar(icos_portal, tmp_path):
    (path,) = fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    sidecar_path(path).unlink()
    fetch("UK-Cvn", tmp_path, client=icos_portal.client())
    assert len(icos_portal.downloads) == 2


def test_fetch_rejects_an_unknown_site(icos_portal, tmp_path):
    with pytest.raises(ValueError, match="UK-Xyz"):
        fetch(["UK-Cvn", "UK-Xyz"], tmp_path, client=icos_portal.client())
    assert not icos_portal.downloads


def test_fetch_rejects_a_download_that_fails_its_hash(make_icos_portal, tmp_path):
    portal = make_icos_portal(corrupt="UK-Cvn")
    with pytest.raises(ProviderError, match="SHA-256"):
        fetch("UK-Cvn", tmp_path, client=portal.client())
    assert not list(tmp_path.iterdir())


def test_provider_errors_carry_the_status(tmp_path):
    def handler(request):
        return httpx.Response(503, text="Service unavailable")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match=r"503.*Service unavailable"):
        sites(client=client)


def test_transport_errors_become_provider_errors():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="could not reach"):
        sites(client=client)


def test_unreadable_site_list_raises():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(ProviderError, match="site list"):
        sites(client=client)
