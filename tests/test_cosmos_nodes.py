import numpy as np
import pytest

from xharvest.cosmos import standardise
from xharvest.cosmos.nodes import cosmos_vwc_snow_masked


def test_masks_snow_days_only(cosmos_raw):
    ds = standardise(cosmos_raw).sel(site="MOORH").dropna("time", subset=["snow"])
    masked = cosmos_vwc_snow_masked(ds.cosmos_vwc, ds.snow)
    snow = ds.snow.values == 1
    assert snow.sum() == 9
    assert np.isnan(masked.values[snow]).all()
    np.testing.assert_array_equal(masked.values[~snow], ds.cosmos_vwc.values[~snow])
    assert masked.attrs["units"] == "%"


def test_keeps_days_with_missing_snow(cosmos_raw):
    ds = standardise(cosmos_raw).sel(site="MOORH")
    ds["snow"] = ds.snow.where(ds.time != ds.time[0])
    masked = cosmos_vwc_snow_masked(ds.cosmos_vwc, ds.snow)
    assert masked.isel(time=0).item() == pytest.approx(
        ds.cosmos_vwc.isel(time=0).item()
    )


def test_accepts_a_gap_in_the_time_axis(cosmos_raw):
    ds = standardise(cosmos_raw).sel(site="MOORH").isel(time=[0, 1, 2, 8, 9, 10])
    masked = cosmos_vwc_snow_masked(ds.cosmos_vwc, ds.snow)
    assert masked.time.equals(ds.time)
