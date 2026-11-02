"""Calls the real COSMOS-UK API. Run with ``just test-live``."""

from datetime import date

import pytest

from xharvest import cosmos

pytestmark = pytest.mark.live


def test_sites():
    found = {s.id: s for s in cosmos.sites()}
    assert found["ALIC1"].lat == pytest.approx(51.15, abs=0.01)


def test_fetch_and_standardise(tmp_path):
    raw = cosmos.fetch(
        "ALIC1",
        date(2025, 1, 1),
        date(2025, 1, 2),
        tmp_path,
        parameters=["cosmos_vwc", "snow"],
    )
    ds = cosmos.standardise(raw)
    assert ds.sizes["time"] == 2
    assert ds.cosmos_vwc.attrs["units"] == "%"
