from contextlib import nullcontext
from datetime import date, datetime

import pytest
import xarray as xr
from typer.testing import CliRunner

from xharvest.cli import main
from xharvest.cli.app import app
from xharvest.cli.cosmos import _date_or_datetime
from xharvest.cosmos import _fetch

runner = CliRunner()


@pytest.fixture
def mock_api(monkeypatch, cosmos_api):
    client = cosmos_api.client()
    monkeypatch.setattr(_fetch, "_client", lambda _: nullcontext(client))
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
    assert mock_api.data_requests[0].url.params["parameter-name"] == "snow,ta"

    out = tmp_path / "cosmos.nc"
    files = [str(p) for p in raw.iterdir()]
    result = runner.invoke(app, ["cosmos", "standardise", *files, "--out", str(out)])
    assert result.exit_code == 0, result.output
    with xr.open_dataset(out) as ds:
        assert set(ds.site.values) == {"MOORH", "ALIC1"}


@pytest.mark.parametrize(
    "args",
    [
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
    monkeypatch.setattr("sys.argv", ["xharvest", "--help"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2025-01-01", date(2025, 1, 1)),
        ("2025-01-01T06:00", datetime(2025, 1, 1, 6)),
        ("2025-01-01 06:00", datetime(2025, 1, 1, 6)),
    ],
)
def test_dates_stay_dates(value, expected):
    parsed = _date_or_datetime(value)
    assert parsed == expected
    assert type(parsed) is type(expected)


def test_bad_dates_are_rejected(mock_api, tmp_path):
    args = ["cosmos", "fetch", "MOORH", "--start", "1 Jan", "--end", "2025-01-02"]
    result = runner.invoke(app, [*args, "--out", str(tmp_path)])
    assert result.exit_code == 2


def test_unknown_collection_lists_the_choices(mock_api):
    result = runner.invoke(app, ["cosmos", "sites", "--collection", "1H"])
    assert result.exit_code == 2
    assert "'1D', '30M'" in result.output
    assert "1D|30M" in runner.invoke(app, ["cosmos", "sites", "--help"]).output
