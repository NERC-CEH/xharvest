"""Download and standardise COSMOS-UK site data.

`sites` and `fetch` need the `cosmos` extra: `pip install xharvest[cosmos]`.
"""

from ._fetch import Collection, Site, fetch, sites
from ._standardise import standardise, to_netcdf
from ._variables import (
    VARIABLES,
    AirTemperature,
    Albedo,
    CosmosVWC,
    D86Depth,
    Precip,
    Snow,
    TdtVWC,
)

__all__ = [
    "VARIABLES",
    "AirTemperature",
    "Albedo",
    "Collection",
    "CosmosVWC",
    "D86Depth",
    "Precip",
    "Site",
    "Snow",
    "TdtVWC",
    "fetch",
    "sites",
    "standardise",
    "to_netcdf",
]
