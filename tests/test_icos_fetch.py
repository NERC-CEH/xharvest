import copy
from urllib.parse import parse_qs

import httpx
import pytest

from xharvest.errors import ProviderError
from xharvest.icos import fetch, stations
from xharvest.provenance import read_sidecar

AMO_FILE = "ICOSETC_UK-AMo_ARCHIVE_INTERIM_L2.zip"


def test_stations_reads_the_station_list(icos_portal):
    found = {s.id: s for s in stations(client=icos_portal.client())}
    assert set(found) == {"DE-Har", "UK-AMo"}
    amo = found["UK-AMo"]
    assert amo.name == "Auchencorth Moss"
    assert amo.file_name == AMO_FILE
    assert amo.lat == pytest.approx(55.79, abs=0.01)
    assert amo.citation.startswith("Nemitz, E.")
    assert "https://creativecommons.org/licenses/by/4.0" in amo.licence
    assert amo.object_id == amo.object_uri.rsplit("/", 1)[-1]


def test_stations_asks_for_current_etc_archives(icos_portal):
    stations(client=icos_portal.client())
    (request,) = icos_portal.requests
    query = parse_qs(request.content.decode())["query"][0]
    assert "etcArchiveProduct" in query
    assert "isNextVersionOf" in query


def test_stations_keeps_the_archive_that_ends_latest(icos_portal):
    # A station can have a current final and a current interim archive.
    bindings = icos_portal.stations["results"]["bindings"]
    har = next(b for b in bindings if b["stationId"]["value"] == "DE-Har")
    interim = copy.deepcopy(har)
    interim["fileName"]["value"] = "ICOSETC_DE-Har_ARCHIVE_INTERIM_L2.zip"
    interim["dobj"]["value"] += "x"
    interim["timeEnd"]["value"] = "2099-01-01T00:00:00Z"
    tie = copy.deepcopy(har)
    tie["fileName"]["value"] = "ICOSETC_DE-Har_ARCHIVE_INTERIM_L2.zip"
    for listing, expected in [
        ([har, interim], "ICOSETC_DE-Har_ARCHIVE_INTERIM_L2.zip"),
        ([tie, har], "ICOSETC_DE-Har_ARCHIVE_L2.zip"),
    ]:
        icos_portal.stations["results"]["bindings"] = listing
        (found,) = stations(client=icos_portal.client())
        assert found.file_name == expected


def test_fetch_writes_archive_and_sidecar(icos_portal, tmp_path):
    (path,) = fetch("UK-AMo", tmp_path / "raw", client=icos_portal.client())
    assert path == tmp_path / "raw" / AMO_FILE
    retrieval = read_sidecar(path)
    assert retrieval.url.startswith("https://data.icos-cp.eu/objects/")
    assert retrieval.metadata["station_id"] == "UK-AMo"
    assert retrieval.metadata["citation"].startswith("Nemitz, E.")
    assert "creativecommons" in retrieval.metadata["licence"]
    assert retrieval.metadata["pid"].startswith("https://hdl.handle.net/11676/")


def test_fetch_returns_paths_in_the_order_given(icos_portal, tmp_path):
    paths = fetch(["UK-AMo", "DE-Har"], tmp_path, client=icos_portal.client())
    assert [p.name for p in paths] == [AMO_FILE, "ICOSETC_DE-Har_ARCHIVE_L2.zip"]


def test_fetch_skips_archives_already_fetched(icos_portal, tmp_path):
    fetch("UK-AMo", tmp_path, client=icos_portal.client())
    fetch("UK-AMo", tmp_path, client=icos_portal.client())
    assert len(icos_portal.downloads) == 1


def test_fetch_refuses_to_replace_an_older_version(icos_portal, tmp_path):
    # Monthly interim versions keep the file name, so a new one is a new object.
    fetch("UK-AMo", tmp_path, client=icos_portal.client())
    for binding in icos_portal.stations["results"]["bindings"]:
        binding["dobj"]["value"] += "x"
    icos_portal.archives = {k + "x": v for k, v in icos_portal.archives.items()}
    with pytest.raises(ValueError, match="overwrite=True"):
        fetch("UK-AMo", tmp_path, client=icos_portal.client())
    fetch("UK-AMo", tmp_path, overwrite=True, client=icos_portal.client())
    assert len(icos_portal.downloads) == 2


def test_fetch_rejects_an_unknown_station(icos_portal, tmp_path):
    with pytest.raises(ValueError, match="UK-Xyz"):
        fetch(["UK-AMo", "UK-Xyz"], tmp_path, client=icos_portal.client())
    assert not icos_portal.downloads


def test_fetch_rejects_a_download_that_fails_its_hash(make_icos_portal, tmp_path):
    portal = make_icos_portal(corrupt="UK-AMo")
    with pytest.raises(ProviderError, match="SHA-256"):
        fetch("UK-AMo", tmp_path, client=portal.client())
    assert not list(tmp_path.iterdir())


def test_provider_errors_carry_the_status():
    def handler(request):
        return httpx.Response(503, text="Service unavailable")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match=r"503.*Service unavailable"):
        stations(client=client)
