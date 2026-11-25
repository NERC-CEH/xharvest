"""Contract types for the variables of the standardised ICOS ancillary Datasets.

Each type declares the CF unit `standardise` writes and the coordinates every
record carries: `site`, `time`, `lat` and `lon`. They declare no `Dims` and no
`Freq`, since measurements are irregular records, not series.

`VARIABLES` maps each group in `GROUPS` to its variables and their types.

Their units need the CF registry: call `xarray_annotated.units.use_cf_units()`.
"""

from typing import Annotated

import xarray as xr
from xarray_annotated import Coords, Unit

from ._pipeline import GROUPS

_RECORD = Coords("site", "time", "lat", "lon")

AreaIndex = Annotated[xr.DataArray, Unit("m2 m-2"), _RECORD]
Biomass = Annotated[xr.DataArray, Unit("kg m-2"), _RECORD]
CanopyHeight = Annotated[xr.DataArray, Unit("m"), _RECORD]
SoilContent = Annotated[xr.DataArray, Unit("%"), _RECORD]
SoilStock = Annotated[xr.DataArray, Unit("g m-2"), _RECORD]

_TYPES = {
    "LAI": AreaIndex,
    "BIOMASS": Biomass,
    "HEIGHTC": CanopyHeight,
    "SOIL_TEX": SoilContent,
    "SOIL_STOCK": SoilStock,
}

VARIABLES = {
    group: dict.fromkeys(names, _TYPES[group]) for group, names in GROUPS.items()
}
