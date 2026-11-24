# ICOS with catena

## Contract types

`xharvest.icos` exports a contract type for each unit in a standardised file, and `VARIABLES`, which maps each variable's name to its type.
Annotate a node's input with one and catena checks the file against it before compute.
Import the module rather than the names, as `from xharvest import icos`, and write `icos.CarbonFlux`.
Each declares the CF unit and the coordinates `time`, `site`, `lat` and `lon`, plus `depth` for the soil profiles.
Types with the same unit and coordinates are the same object, so a type does not tell variables apart.
None declares a `Freq`; add one where it matters, as `Annotated[icos.CarbonFlux, Freq("D")]`.
Their units need `xarray_annotated.units.use_cf_units()`.

| Type | Unit | Variables |
|---|---|---|
| `AirTemperature` | `degC` | `TA_F` |
| `VapourPressureDeficit` | `hPa` | `VPD_F` |
| `Precip` | `mm d-1` | `P_F` |
| `EnergyFlux` | `W m-2` | `SW_IN_F`, `LW_IN_F`, `NETRAD`, `G_F_MDS`, `LE_F_MDS`, `LE_CORR`, `LE_CORR_JOINTUNC`, `H_F_MDS`, `H_CORR` |
| `AirPressure` | `kPa` | `PA_F` |
| `WindSpeed` | `m s-1` | `WS_F` |
| `PhotonFlux` | `umol m-2 s-1` | `PPFD_IN` |
| `CO2MoleFraction` | `umol mol-1` | `CO2_F_MDS` |
| `CarbonFlux` | `g m-2 d-1` | `NEE_VUT_REF`, `NEE_VUT_REF_JOINTUNC`, `GPP_NT_VUT_REF`, `GPP_DT_VUT_REF`, `RECO_NT_VUT_REF`, `RECO_DT_VUT_REF` |
| `QualityFraction` | `1` | The `_QC` of each variable on `(time, site)` |
| `SoilWaterContent` | `%` | `SWC_F_MDS` |
| `SoilTemperature` | `degC` | `TS_F_MDS` |
| `ProfileQualityFraction` | `1` | `SWC_F_MDS_QC`, `TS_F_MDS_QC` |

There are no catena nodes yet.
