"""Download and standardise FLUXNET data from the ICOS Carbon Portal.

`sites` and `fetch` need the `icos` extra:
`pip install "xharvest[icos] @ git+https://github.com/NERC-CEH/xharvest"`.
"""

from ._fetch import Site, fetch, sites
from ._pipeline import PROFILES, QC, SCALARS
from ._standardise import standardise, to_netcdf
from ._variables import (
    VARIABLES,
    AirPressure,
    AirTemperature,
    CarbonFlux,
    CO2MoleFraction,
    EnergyFlux,
    PhotonFlux,
    Precip,
    ProfileQualityFraction,
    QualityFraction,
    SoilTemperature,
    SoilWaterContent,
    VapourPressureDeficit,
    WindSpeed,
)

__all__ = [
    "PROFILES",
    "QC",
    "SCALARS",
    "VARIABLES",
    "AirPressure",
    "AirTemperature",
    "CO2MoleFraction",
    "CarbonFlux",
    "EnergyFlux",
    "PhotonFlux",
    "Precip",
    "ProfileQualityFraction",
    "QualityFraction",
    "Site",
    "SoilTemperature",
    "SoilWaterContent",
    "VapourPressureDeficit",
    "WindSpeed",
    "fetch",
    "sites",
    "standardise",
    "to_netcdf",
]
