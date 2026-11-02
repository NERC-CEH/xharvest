"""conduit node functions for COSMOS-UK data.

conduit finds this module under the config section ``[cosmos]`` once
``xharvest`` is installed. The functions name their inputs after the
standardised variables, so read the standardised file with ``suffix = ""``:

```toml
[inputs.cosmos]
path = "data/cosmos.nc"
suffix = ""
vars = ["cosmos_vwc", "snow"]

[cosmos]
```

Converting volumetric water content from percent to a fraction needs no node: a
consumer that declares ``Unit("m3 m-3")`` gets the conversion from conduit.
"""

from typing import Annotated

import xarray as xr
from xarray_annotated.temporal import Freq, declare_freq
from xarray_annotated.units import Unit, declare_units, use_cf_units

use_cf_units()

DailyPercent = Annotated[xr.DataArray, Unit("%"), Freq("D")]
DailyFlag = Annotated[xr.DataArray, Unit("1"), Freq("D")]


@declare_units
@declare_freq
def cosmos_vwc_snow_masked(cosmos_vwc: DailyPercent, snow: DailyFlag) -> DailyPercent:
    """Daily COSMOS volumetric water content, NaN on snow days.

    Snow on the ground inflates the neutron signal, so on snow days COSMOS-UK
    reports a VWC estimated from the counts before the snow. Use this node where
    only VWC derived from that day's counts will do; use ``cosmos_vwc`` to keep
    the estimates. Days where ``snow`` is missing are kept.
    """
    return cosmos_vwc.where(snow != 1)
