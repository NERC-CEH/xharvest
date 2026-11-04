"""Run a small conduit pipeline over standardised COSMOS-UK data.

This is the only test that needs conduit. It checks that conduit reads the
standardised file as-is, finds the node module through the ``conduit.modules``
entry point, and passes the whole-DAG contract check.
"""

import textwrap

import numpy as np
import pytest

pytest.skip(
    "pinned conduit does not support xarray-annotated 0.7 yet",
    allow_module_level=True,
)

conduit = pytest.importorskip("conduit")

from xharvest.cosmos import standardise, to_netcdf  # noqa: E402

CONSUMER = """
from typing import Annotated

import xarray as xr
import xarray_annotated as xra
from xarray_annotated import Freq, Unit
from xarray_annotated.units import use_cf_units

use_cf_units()

Percent = Annotated[xr.DataArray, Unit("%"), Freq("D")]
Fraction = Annotated[xr.DataArray, Unit("m3 m-3"), Freq("D")]


@xra.enforce
def vwc_fraction(cosmos_vwc_snow_masked: Percent) -> Fraction:
    return xra.units.convert(cosmos_vwc_snow_masked, "m3 m-3")
"""

CONFIG = """
[inputs.cosmos]
path = "cosmos.nc"
suffix = ""
vars = ["cosmos_vwc", "snow"]

[cosmos]

[consumer]
_import_path = "consumer.py"

[outputs.result]
path = "result.nc"
suffix = ""
vars = ["cosmos_vwc_snow_masked", "vwc_fraction"]
"""


@pytest.fixture
def config(cosmos_raw, tmp_path):
    to_netcdf(cosmos_raw, tmp_path / "cosmos.nc")
    (tmp_path / "consumer.py").write_text(textwrap.dedent(CONSUMER))
    path = tmp_path / "pipeline.toml"
    path.write_text(CONFIG)
    return path


def test_dry_run_finds_the_registered_module(config):
    report = conduit.dry_run(config)
    detail = report.stages[0].detail
    assert "[cosmos] provided by xharvest" in detail
    assert "xharvest.cosmos.nodes" in detail


def test_run(config, cosmos_raw):
    report = conduit.run(config)
    result = report.outputs["result"]
    expected = standardise(cosmos_raw)
    masked = expected.cosmos_vwc.where(expected.snow != 1)

    np.testing.assert_allclose(
        result.cosmos_vwc_snow_masked,
        masked.transpose(*result.cosmos_vwc_snow_masked.dims),
    )
    np.testing.assert_allclose(
        result.vwc_fraction, masked.transpose(*result.vwc_fraction.dims) / 100
    )
    assert result.vwc_fraction.attrs["units"] == "m3 m-3"
    assert (config.parent / "result.nc").exists()
