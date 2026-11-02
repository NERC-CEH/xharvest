import pytest

from xharvest.provenance import (
    Retrieval,
    history_line,
    is_fetched,
    is_sidecar,
    read_sidecar,
    save,
    sidecar_path,
)

URL = "https://example.org/data"


def test_save_round_trip(tmp_path):
    path = tmp_path / "raw.json"
    written = save(path, b"data", URL, {"a": 1, "b": "x"})
    assert path.read_bytes() == b"data"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["raw.json", "raw.meta.json"]
    assert is_sidecar(sidecar_path(path))
    assert not is_sidecar(path)
    assert read_sidecar(path) == written
    assert written.retrieved.endswith("Z")


def test_missing_sidecar(tmp_path):
    with pytest.raises(FileNotFoundError, match="no provenance sidecar"):
        read_sidecar(tmp_path / "raw.json")


@pytest.mark.parametrize(
    ("params", "url"),
    [({"a": 1, "b": "x"}, "https://e.org/d?a=1&b=x"), ({}, "https://e.org/d")],
)
def test_history_line(params, url):
    retrieval = Retrieval("https://e.org/d", params, "2025-01-01T00:00:00Z", "me 1")
    assert history_line(retrieval) == f"2025-01-01T00:00:00Z retrieved {url} (me 1)"


def test_is_fetched_needs_the_data_and_its_sidecar(tmp_path):
    path = tmp_path / "raw.json"
    assert not is_fetched(path, URL, {})
    path.write_bytes(b"interrupted")
    assert not is_fetched(path, URL, {})
    save(path, b"data", URL, {"a": [1, 2]})
    assert is_fetched(path, URL, {"a": [1, 2]})


@pytest.mark.parametrize(
    ("url", "params"),
    [(URL, {"a": [1, 3]}), (URL, {}), (URL + "/other", {"a": [1, 2]})],
)
def test_is_fetched_rejects_a_different_request(tmp_path, url, params):
    path = tmp_path / "raw.json"
    save(path, b"data", URL, {"a": [1, 2]})
    with pytest.raises(ValueError, match="holds a different request"):
        is_fetched(path, url, params)


def test_save_leaves_nothing_behind_when_it_fails(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("xharvest.provenance.os.replace", fail)
    with pytest.raises(OSError, match="disk full"):
        save(tmp_path / "raw.json", b"data", URL, {})
    assert not list(tmp_path.iterdir())
