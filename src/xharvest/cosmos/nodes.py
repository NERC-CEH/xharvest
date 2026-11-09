"""Nodes that catena finds under the config section `[cosmos]`."""

import xarray_annotated as xra
from xarray_annotated.units import use_cf_units

from ._variables import CosmosVWC, Snow

use_cf_units()


@xra.check_annotations
def cosmos_vwc_snow_masked(cosmos_vwc: CosmosVWC, snow: Snow) -> CosmosVWC:
    """Daily COSMOS volumetric water content, NaN on snow days.

    Snow on the ground inflates the neutron signal, so on snow days COSMOS-UK
    reports a VWC estimated from the counts before the snow. Use this node where
    only VWC derived from that day's counts will do; use `cosmos_vwc` to keep
    the estimates. Days where `snow` is missing are kept.

    Declares no `Freq`, since masking works day by day: a gap in the time axis, left
    by joining files from separate periods, is fine here.
    """
    return cosmos_vwc.where(snow != 1)
