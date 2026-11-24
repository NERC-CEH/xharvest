# COSMOS-UK with catena

## Contract types

`xharvest.cosmos` exports a contract type for seven of the [variables](index.md#variables), those the test fixtures cover, and `VARIABLES`, which maps each of their names to its type.
Annotate a node's input with one and catena checks the file against it before compute.
Import the module rather than the names, as `from xharvest import cosmos`, and write `cosmos.Precip`: the module keeps them apart from other providers' types.
Each declares the API's unit and the coordinates `time`, `site`, `lat` and `lon`, which one site selected with `.sel(site=...)` still carries.
Types with the same unit are the same object (`cosmos.Albedo is cosmos.Snow`), so a type does not tell variables apart: catena checks a file against a type's declarations, not its name.
None declares a `Freq`; add one where it matters, as `Annotated[cosmos.CosmosVWC, Freq("D")]`.
Their units need `xarray_annotated.units.use_cf_units()`.

| Variable | Type | Unit |
|---|---|---|
| `albedo` | `Albedo` | `1` |
| `cosmos_vwc` | `CosmosVWC` | `%` |
| `d86_75m` | `D86Depth` | `cm` |
| `precip` | `Precip` | `mm` |
| `snow` | `Snow` | `1` |
| `ta` | `AirTemperature` | `degC` |
| `tdt3_vwc` | `TdtVWC` | `%` |

## Catena nodes

catena finds these nodes under the config section `[cosmos]` once xharvest is installed.
They name their inputs after the standardised variables, so a file read with `suffix = ""` needs nothing more:

```toml
[inputs.cosmos]
path = "data/cosmos.nc"
suffix = ""
vars = ["cosmos_vwc", "snow"]

[cosmos]
```

To keep COSMOS-UK variables apart from another provider's, give the input section a suffix and set the same one as `cosmos_suffix`.
Every node then reads and produces names with that suffix, so `cosmos_vwc_snow_masked` becomes `cosmos_vwc_snow_masked_cosmos`, reading `cosmos_vwc_cosmos` and `snow_cosmos`:

```toml
[inputs.cosmos]
path = "data/cosmos.nc"
suffix = "_cosmos"
vars = ["cosmos_vwc", "snow"]

[cosmos]
cosmos_suffix = "_cosmos"
```

Leaving out `suffix` gives the same result, since catena's default suffix is `_<label>`.
If the two disagree, the build fails on an unbound input.

These nodes keep the API's units, and a node declaring a different unit for its input raises rather than converts.
A node that wants another unit takes the contract type and converts in its body:

```python
from typing import Annotated

import xarray as xr
import xarray_annotated as xra
from xarray_annotated import Unit
from xarray_annotated.units import use_cf_units

from xharvest import cosmos

use_cf_units()

Fraction = Annotated[xr.DataArray, Unit("m3 m-3")]


@xra.check_annotations
def vwc_fraction(cosmos_vwc_snow_masked: cosmos.CosmosVWC) -> Fraction:
    return xra.units.convert(cosmos_vwc_snow_masked, "m3 m-3")
```

::: xharvest.cosmos.nodes.cosmos_vwc_snow_masked
    options:
      heading_level: 3
