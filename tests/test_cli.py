import importlib
from contextlib import nullcontext

import pytest
import xarray as xr
from typer.testing import CliRunner

from conduit_data.cli import main
from conduit_data.cli.app import app

fetch_module = importlib.import_module("conduit_data.cosmos.fetch")
runner = CliRunner()


@pytest.fixture
def mock_api(monkeypatch, cosmos_api):
    client = cosmos_api.client()
    monkeypatch.setattr(fetch_module, "_client", lambda _: nullcontext(client))
    return cosmos_api


def test_sites(mock_api):
    result = runner.invoke(app, ["cosmos", "sites"])
    assert result.exit_code == 0, result.output
    assert "ALIC1\tAlice Holt\t51.15355\t-0.85823" in result.output


def test_fetch_then_standardise(mock_api, tmp_path):
    raw = tmp_path / "raw"
    result = runner.invoke(
        app,
        [
            "cosmos",
            "fetch",
            "MOORH",
            "ALIC1",
            "--start",
            "2025-01-01",
            "--end",
            "2025-01-14",
            "--out",
            str(raw),
            "--parameter",
            "snow",
            "--parameter",
            "ta",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 2
    assert mock_api.requests[0].url.params["parameter-name"] == "snow,ta"

    out = tmp_path / "cosmos.nc"
    files = [str(p) for p in raw.iterdir()]
    result = runner.invoke(app, ["cosmos", "standardise", *files, "--out", str(out)])
    assert result.exit_code == 0, result.output
    with xr.open_dataset(out) as ds:
        assert set(ds.site.values) == {"MOORH", "ALIC1"}


@pytest.mark.parametrize(
    "args",
    [
        ["sites", "--collection", "1H"],
        ["fetch", "NOPE", "--start", "2025-01-01", "--end", "2025-01-02", "--out", "x"],
        ["standardise", "missing.json", "--out", "x.nc"],
    ],
)
def test_errors_exit_cleanly(mock_api, tmp_path, monkeypatch, args):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["cosmos", *args])
    assert result.exit_code == 1
    assert result.output.startswith("Error: ")
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_main_runs_the_app(monkeypatch):
    monkeypatch.setattr("sys.argv", ["conduit-data", "--help"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 0
