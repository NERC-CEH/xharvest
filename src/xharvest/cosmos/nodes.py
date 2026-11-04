"""Nodes that conduit finds under the config section `[cosmos]`.

They name their inputs after the standardised variables, so conduit must read the
standardised file with `suffix = ""`.
"""

from typing import Annotated

import xarray as xr
import xarray_annotated as xra
from xarray_annotated import Freq, Unit
from xarray_annotated.units import use_cf_units

use_cf_units()

DailyPercent = Annotated[xr.DataArray, Unit("%"), Freq("D")]
DailyFlag = Annotated[xr.DataArray, Unit("1"), Freq("D")]


@xra.enforce
def cosmos_vwc_snow_masked(cosmos_vwc: DailyPercent, snow: DailyFlag) -> DailyPercent:
    """Daily COSMOS volumetric water content, NaN on snow days.

    Snow on the ground inflates the neutron signal, so on snow days COSMOS-UK
    reports a VWC estimated from the counts before the snow. Use this node where
    only VWC derived from that day's counts will do; use `cosmos_vwc` to keep
    the estimates. Days where `snow` is missing are kept.
    """
    return cosmos_vwc.where(snow != 1)
