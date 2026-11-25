"""Contract types for the variables of a standardised FLUXNET Dataset.

Each type declares the CF unit `standardise` writes and the coordinates the variable
carries: `time`, `site`, `lat` and `lon`, and `depth` for the soil profiles. They
declare no `Dims`, so one site selected out of the `site` dim passes too, and no
`Freq`; add one where it matters, as `Annotated[fluxnet.CarbonFlux, Freq("D")]`.

`VARIABLES` maps each standardised variable to its type.

Their units need the CF registry: call `xarray_annotated.units.use_cf_units()`.
"""

from typing import Annotated

import xarray as xr
from xarray_annotated import Coords, Unit

_SITE = Coords("time", "site", "lat", "lon")
_PROFILE = Coords("time", "site", "lat", "lon", "depth")

AirTemperature = Annotated[xr.DataArray, Unit("degC"), _SITE]
VapourPressureDeficit = Annotated[xr.DataArray, Unit("hPa"), _SITE]
Precip = Annotated[xr.DataArray, Unit("mm d-1"), _SITE]
EnergyFlux = Annotated[xr.DataArray, Unit("W m-2"), _SITE]
AirPressure = Annotated[xr.DataArray, Unit("kPa"), _SITE]
WindSpeed = Annotated[xr.DataArray, Unit("m s-1"), _SITE]
PhotonFlux = Annotated[xr.DataArray, Unit("umol m-2 s-1"), _SITE]
CO2MoleFraction = Annotated[xr.DataArray, Unit("umol mol-1"), _SITE]
CarbonFlux = Annotated[xr.DataArray, Unit("g m-2 d-1"), _SITE]
QualityFraction = Annotated[xr.DataArray, Unit("1"), _SITE]
SoilWaterContent = Annotated[xr.DataArray, Unit("%"), _PROFILE]
SoilTemperature = Annotated[xr.DataArray, Unit("degC"), _PROFILE]
ProfileQualityFraction = Annotated[xr.DataArray, Unit("1"), _PROFILE]

VARIABLES = {
    "TA_F": AirTemperature,
    "VPD_F": VapourPressureDeficit,
    "P_F": Precip,
    "SW_IN_F": EnergyFlux,
    "LW_IN_F": EnergyFlux,
    "PA_F": AirPressure,
    "WS_F": WindSpeed,
    "PPFD_IN": PhotonFlux,
    "NETRAD": EnergyFlux,
    "CO2_F_MDS": CO2MoleFraction,
    "G_F_MDS": EnergyFlux,
    "LE_F_MDS": EnergyFlux,
    "LE_CORR": EnergyFlux,
    "LE_CORR_JOINTUNC": EnergyFlux,
    "H_F_MDS": EnergyFlux,
    "H_CORR": EnergyFlux,
    "NEE_VUT_REF": CarbonFlux,
    "NEE_VUT_REF_JOINTUNC": CarbonFlux,
    "GPP_NT_VUT_REF": CarbonFlux,
    "GPP_DT_VUT_REF": CarbonFlux,
    "RECO_NT_VUT_REF": CarbonFlux,
    "RECO_DT_VUT_REF": CarbonFlux,
    **{
        f"{name}_QC": QualityFraction
        for name in [
            "TA_F",
            "VPD_F",
            "P_F",
            "SW_IN_F",
            "LW_IN_F",
            "PA_F",
            "WS_F",
            "PPFD_IN",
            "NETRAD",
            "CO2_F_MDS",
            "G_F_MDS",
            "LE_F_MDS",
            "H_F_MDS",
            "NEE_VUT_REF",
        ]
    },
    "SWC_F_MDS": SoilWaterContent,
    "SWC_F_MDS_QC": ProfileQualityFraction,
    "TS_F_MDS": SoilTemperature,
    "TS_F_MDS_QC": ProfileQualityFraction,
}
