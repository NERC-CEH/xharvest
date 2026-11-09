"""Contract types for the variables of a standardised COSMOS-UK Dataset.

Each type declares the unit `standardise` writes and the coordinates every variable
carries. Annotate a node's parameter with one and catena checks the file against it
before compute. They declare no `Dims`, so one site selected out of the `site` dim
passes too, and no `Freq`, which depends on the collection and on whether a consumer
accepts gaps; add one where it matters, as `Annotated[cosmos.CosmosVWC, Freq("D")]`.

`VARIABLES` maps each standardised variable to its type. The contract tests check
the fixtures against it, so it covers the `1D` collection only.

Their units need the CF registry: call `xarray_annotated.units.use_cf_units()`.
"""

from typing import Annotated

import xarray as xr
from xarray_annotated import Coords, Unit

_SITE_COORDS = Coords("time", "site", "lat", "lon")

Albedo = Annotated[xr.DataArray, Unit("1"), _SITE_COORDS]
CosmosVWC = Annotated[xr.DataArray, Unit("%"), _SITE_COORDS]
D86Depth = Annotated[xr.DataArray, Unit("cm"), _SITE_COORDS]
Precip = Annotated[xr.DataArray, Unit("mm"), _SITE_COORDS]
Snow = Annotated[xr.DataArray, Unit("1"), _SITE_COORDS]
AirTemperature = Annotated[xr.DataArray, Unit("degC"), _SITE_COORDS]
TdtVWC = Annotated[xr.DataArray, Unit("%"), _SITE_COORDS]

VARIABLES = {
    "albedo": Albedo,
    "cosmos_vwc": CosmosVWC,
    "d86_75m": D86Depth,
    "precip": Precip,
    "snow": Snow,
    "ta": AirTemperature,
    "tdt3_vwc": TdtVWC,
}
