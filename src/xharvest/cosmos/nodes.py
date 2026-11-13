"""Nodes that catena finds under the config section `[cosmos]`."""

from typing import Annotated

import xarray_annotated as xra
from xarray_annotated.units import use_cf_units

from ._variables import CosmosVWC, Snow

use_cf_units()

# Daily data only; the 30-minute collection is deferred to NERC-CEH/xharvest#8.

_DAILY = xra.Freq("D", gaps_ok=True)
DailyVWC = Annotated[CosmosVWC, _DAILY]
DailySnow = Annotated[Snow, _DAILY]


@xra.check_annotations
def cosmos_vwc_snow_masked(cosmos_vwc: DailyVWC, snow: DailySnow) -> DailyVWC:
    """Daily COSMOS volumetric water content, NaN on snow days.

    Snow on the ground inflates the neutron signal, so on snow days COSMOS-UK
    reports a VWC estimated from the counts before the snow. Use this node where
    only VWC derived from that day's counts will do; use `cosmos_vwc` to keep
    the estimates. Days where `snow` is missing are kept.

    Declares `Freq("D", gaps_ok=True)`: masking works day by day, so a gap in the
    time axis, left by joining files from separate periods, is fine here, but
    sub-daily data is rejected.
    """
    return cosmos_vwc.where(snow != 1)
