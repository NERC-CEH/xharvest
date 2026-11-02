import pytest

from conduit_data.provenance import (
    Retrieval,
    history_line,
    is_sidecar,
    read_sidecar,
    sidecar_path,
    write_sidecar,
)


def test_sidecar_round_trip(tmp_path):
    path = tmp_path / "raw.json"
    written = write_sidecar(path, "https://example.org/data", {"a": 1, "b": "x"})
    assert sidecar_path(path).name == "raw.meta.json"
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
