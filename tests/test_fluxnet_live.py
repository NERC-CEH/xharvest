"""Calls the real ICOS Carbon Portal. Run with ``just test-live``.

Besides checking `fetch` and `standardise` against the portal, this re-checks what
the provider page says a daily value means, against the half-hourly file in the
same archive. It downloads UK-Cvn's archive (27 MB) once.
"""

import csv
import io
import zipfile

import numpy as np
import pytest

from xharvest import fluxnet
from xharvest.fluxnet import _archive as fx

pytestmark = pytest.mark.live

SITE = "UK-Cvn"


@pytest.fixture(scope="module")
def archive_path(tmp_path_factory):
    (path,) = fluxnet.fetch(SITE, tmp_path_factory.mktemp("fluxnet"))
    return path


@pytest.fixture(scope="module")
def half_hourly(archive_path):
    """The half-hourly file: (period starts on the file's clock, columns)."""
    with zipfile.ZipFile(archive_path) as archive:
        (name,) = [n for n in archive.namelist() if "_FLUXMET_HH_" in n]
        rows = list(csv.reader(io.StringIO(archive.read(name).decode("ascii"))))
    header = rows[0]
    starts = np.array(
        [
            f"{r[0][:4]}-{r[0][4:6]}-{r[0][6:8]}T{r[0][8:10]}:{r[0][10:12]}"
            for r in rows[1:]
        ],
        dtype="datetime64[m]",
    )
    values = np.array([r for r in rows[1:]], dtype=float)
    values[values == -9999] = np.nan
    return starts, {name: values[:, i] for i, name in enumerate(header)}


def test_sites():
    found = {s.id: s for s in fluxnet.sites()}
    assert found[SITE].name == "Coveney"
    assert found[SITE].file_name.startswith("EUF_UK-Cvn_FLUXNET_")


def test_fetch_and_standardise(archive_path):
    ds = fluxnet.standardise([archive_path])
    assert ds.sizes["time"] >= 365
    assert ds.TA_F.attrs["units"] == "degC"
    assert ds.SWC_F_MDS.notnull().any()


def _daily(starts, values, how):
    days = starts.astype("datetime64[D]")
    unique = np.unique(days)
    reduce = np.nansum if how == "sum" else np.nanmean
    out = np.array([reduce(values[days == d]) for d in unique])
    complete = np.array([np.isfinite(values[days == d]).all() for d in unique])
    return unique, np.where(complete, out, np.nan)


@pytest.mark.parametrize(
    ("name", "how", "tolerance"),
    [("TA_F", "mean", 1e-3), ("SW_IN_F", "mean", 1e-3), ("P_F", "sum", 1e-2)],
)
def test_a_daily_value_covers_the_local_day(
    archive_path, half_hourly, name, how, tolerance
):
    # Daily means (and the precipitation rate in mm d-1) are of the half-hours
    # starting within the day on the file's clock.
    starts, columns = half_hourly
    days, expected = _daily(starts, columns[name], how)
    texts = fx.archive_texts([archive_path])
    table = fx.tables(fx.raw_tables(texts))[archive_path]
    daily = dict(zip(table.dates, table.columns[name], strict=True))
    found = np.array([daily.get(d, np.nan) for d in days])
    both = np.isfinite(found) & np.isfinite(expected)
    assert both.sum() > 300
    assert np.max(np.abs(found[both] - expected[both])) < tolerance


def test_the_file_clock_is_local_standard_time(archive_path, half_hourly):
    # SW_IN_POT, computed by ONEFlux, peaks at solar noon. At UTC + UTC_OFFSET,
    # that is 12:00 - lon / 15 + offset, give or take the equation of time
    # (16 min); local solar time would put it at 12:00 whatever the longitude.
    starts, columns = half_hourly
    site = fx.sites(fx.archive_texts([archive_path]))[archive_path]
    potential = columns["SW_IN_POT"]
    days = starts.astype("datetime64[D]")
    peaks = []
    for day in np.unique(days):
        today = np.flatnonzero(days == day)
        if np.isfinite(potential[today]).all():
            peak = starts[today[np.argmax(potential[today])]]
            peaks.append((peak - day).astype(float) / 60 + 0.25)
    expected = 12 - site.lon / 15 + site.utc_offset
    assert abs(np.median(peaks) - expected) < 0.5
