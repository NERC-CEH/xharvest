# ICOS with catena

## Contract types

`xharvest.icos` exports a contract type for each unit in a standardised Dataset, and `VARIABLES`, which maps each group to its variables and their types.
Annotate a node's input with one and catena checks the file against it before compute.
Import the module rather than the names, as `from xharvest import icos`, and write `icos.AreaIndex`.
Each declares the CF unit and the coordinates every record carries: `site`, `time`, `lat` and `lon`.
Types with the same unit and coordinates are the same object, so a type does not tell variables apart.
None declares `Dims` or a `Freq`, since the records are irregular measurements rather than series.
Their units need `xarray_annotated.units.use_cf_units()`.

| Type | Unit | Group | Variables |
|---|---|---|---|
| `AreaIndex` | `m2 m-2` | `LAI` | `LAI` |
| `Biomass` | `kg m-2` | `BIOMASS` | `BIOMASS` |
| `CanopyHeight` | `m` | `HEIGHTC` | `HEIGHTC`, `HEIGHTC_U` |
| `SoilContent` | `%` | `SOIL_TEX` | `SOIL_TEX_SAND`, `SOIL_TEX_SILT`, `SOIL_TEX_CLAY`, `SOIL_TEX_ROCK`, `SOIL_TEX_FIELD_CAP`, `SOIL_TEX_WILT`, `SOIL_TEX_SAT`, `SOIL_TEX_WATER_HOLD_CAP` |
| `SoilStock` | `g m-2` | `SOIL_STOCK` | `SOIL_STOCK_C_ORG`, `SOIL_STOCK_N_TOT`, `SOIL_STOCK_P`, `SOIL_STOCK_K` |

There are no catena nodes yet.
A model's drivers want a value per site, or per site and day, so a pipeline must first select the records it needs, by their qualifiers, and combine them; that choice is the pipeline's to make.
