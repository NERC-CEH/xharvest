import json
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from xharvest.cosmos import _fetch, fetch, sites
from xharvest.errors import ProviderError
from xharvest.provenance import read_sidecar, sidecar_path


def test_sites_reads_lat_lon_the_right_way_round(cosmos_api):
    found = {s.id: s for s in sites(client=cosmos_api.client())}
    alic = found["ALIC1"]
    assert (alic.id, alic.name) == ("ALIC1", "Alice Holt")
    assert (alic.lat, alic.lon) == pytest.approx((51.153551, -0.858232))
    assert alic.period.startswith("2015-03-06")
    assert 49 < found["MOORH"].lat < 61
    assert -9 < found["MOORH"].lon < 2


def test_lat_lon_reads_either_order():
    assert _fetch._lat_lon([-0.86, 51.15]) == (51.15, -0.86)
    assert _fetch._lat_lon([51.15, -0.86]) == (51.15, -0.86)


def test_fetch_requests_full_iso_datetimes(cosmos_api, tmp_path):
    fetch(
        "MOORH",
        date(2025, 1, 1),
        datetime(2025, 1, 14, 12),
        tmp_path,
        parameters=["snow", "cosmos_vwc"],
        client=cosmos_api.client(),
    )
    (request,) = cosmos_api.data_requests
    assert request.url.path == "/collections/1D/locations/MOORH"
    assert request.url.params["datetime"] == (
        "2025-01-01T00:00:00Z/2025-01-14T12:00:00Z"
    )
    assert request.url.params["parameter-name"] == "snow,cosmos_vwc"


def test_fetch_converts_aware_datetimes_to_utc(cosmos_api, tmp_path):
    plus_one = timezone(timedelta(hours=1))
    fetch(
        "MOORH",
        datetime(2025, 1, 1, 1, tzinfo=plus_one),
        datetime(2025, 1, 2, tzinfo=UTC),
        tmp_path,
        client=cosmos_api.client(),
    )
    (request,) = cosmos_api.data_requests
    assert request.url.params["datetime"].startswith("2025-01-01T00:00:00Z/")
    assert "parameter-name" not in request.url.params


def test_fetch_writes_one_file_and_sidecar_per_site(cosmos_api, tmp_path):
    out = tmp_path / "new" / "dir"
    paths = fetch(
        ["MOORH", "ALIC1"],
        date(2025, 1, 1),
        date(2025, 1, 14),
        out,
        client=cosmos_api.client(),
    )
    assert [p.name for p in paths] == [
        "MOORH_1D_20250101_20250114.json",
        "ALIC1_1D_20250101_20250114.json",
    ]
    for path in paths:
        assert json.loads(path.read_text())["type"] == "CoverageCollection"
        retrieval = read_sidecar(path)
        assert retrieval.url.endswith(path.name.split("_")[0])
        assert retrieval.params["datetime"].startswith("2025-01-01T00:00:00Z")
        assert retrieval.agent.startswith("xharvest ")
    assert read_sidecar(paths[0]).metadata == {"site_names": {"MOORH": "Moor House"}}
    assert read_sidecar(paths[1]).metadata == {"site_names": {"ALIC1": "Alice Holt"}}


def test_fetch_skips_existing_files_unless_overwrite(cosmos_api, tmp_path):
    args = ("MOORH", date(2025, 1, 1), date(2025, 1, 14), tmp_path)
    (path,) = fetch(*args, client=cosmos_api.client())
    path.write_text("sentinel")
    requests_so_far = len(cosmos_api.requests)
    fetch(*args, client=cosmos_api.client())
    assert path.read_text() == "sentinel"
    assert len(cosmos_api.requests) == requests_so_far

    fetch(*args, overwrite=True, client=cosmos_api.client())
    assert path.read_text() != "sentinel"
    assert len(cosmos_api.data_requests) == 2


def test_fetch_refuses_to_reuse_a_file_from_another_request(cosmos_api, tmp_path):
    args = ("MOORH", date(2025, 1, 1), date(2025, 1, 14), tmp_path)
    fetch(*args, parameters=["snow"], client=cosmos_api.client())
    with pytest.raises(ValueError, match="holds a different request"):
        fetch(*args, client=cosmos_api.client())
    assert len(cosmos_api.data_requests) == 1
    fetch(*args, overwrite=True, client=cosmos_api.client())
    assert (
        "parameter-name"
        not in read_sidecar(tmp_path / "MOORH_1D_20250101_20250114.json").params
    )


def test_fetch_downloads_again_after_an_interrupted_download(cosmos_api, tmp_path):
    args = ("MOORH", date(2025, 1, 1), date(2025, 1, 14), tmp_path)
    (path,) = fetch(*args, client=cosmos_api.client())
    sidecar_path(path).unlink()
    path.write_text("truncated")
    fetch(*args, client=cosmos_api.client())
    assert len(cosmos_api.data_requests) == 2
    assert json.loads(path.read_text())["type"] == "CoverageCollection"


def test_fetch_names_files_by_time_when_given_datetimes(cosmos_api, tmp_path):
    (path,) = fetch(
        "MOORH",
        datetime(2025, 1, 1, 6),
        datetime(2025, 1, 2, 12, 30),
        tmp_path,
        client=cosmos_api.client(),
    )
    assert path.name == "MOORH_1D_20250101T060000_20250102T123000.json"


def test_fetch_raises_the_apis_message(cosmos_api, tmp_path):
    with pytest.raises(ProviderError, match=r"400: Invalid location ID\(s\)"):
        fetch(
            "NOPE",
            date(2025, 1, 1),
            date(2025, 1, 2),
            tmp_path,
            client=cosmos_api.client(),
        )
    assert not list(tmp_path.iterdir())


def test_fetch_falls_back_to_body_text_on_unexpected_errors(tmp_path):
    import httpx

    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503, text="down"))
    )
    with pytest.raises(ProviderError, match="503: down"):
        fetch("ALIC1", date(2025, 1, 1), date(2025, 1, 2), tmp_path, client=client)


def test_fetch_leaves_a_callers_client_open(cosmos_api, tmp_path):
    client = cosmos_api.client()
    fetch("MOORH", date(2025, 1, 1), date(2025, 1, 2), tmp_path, client=client)
    assert not client.is_closed


def test_sites_rejects_unknown_collection():
    with pytest.raises(ValueError, match="unknown COSMOS-UK collection '1H'"):
        sites("1H")  # type: ignore[arg-type]


def test_fetch_rejects_unknown_collection(tmp_path):
    start, end = date(2025, 1, 1), date(2025, 1, 2)
    with pytest.raises(ValueError, match="unknown COSMOS-UK collection '1H'"):
        fetch("ALIC1", start, end, tmp_path, collection="1H")  # type: ignore[arg-type]
