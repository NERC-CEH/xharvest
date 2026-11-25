"""Download and standardise ICOS ecosystem stations' ancillary measurements.

The ETC L2 archives on the ICOS Carbon Portal hold, besides each station's
fluxes, its ancillary measurements: LAI, biomass, canopy height and soil
properties. `standardise` reads one group of them at a time, as records.

`stations` and `fetch` need the `icos` extra:
`pip install "xharvest[icos] @ git+https://github.com/NERC-CEH/xharvest"`.
"""

from ._fetch import Station, fetch, stations
from ._pipeline import GROUPS
from ._standardise import standardise, to_netcdf
from ._variables import (
    VARIABLES,
    AreaIndex,
    Biomass,
    CanopyHeight,
    SoilContent,
    SoilStock,
)

__all__ = [
    "GROUPS",
    "VARIABLES",
    "AreaIndex",
    "Biomass",
    "CanopyHeight",
    "SoilContent",
    "SoilStock",
    "Station",
    "fetch",
    "standardise",
    "stations",
    "to_netcdf",
]
