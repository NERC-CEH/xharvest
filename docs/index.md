# xharvest

Download environmental data from its providers, and standardise it into netCDF that [catena](https://github.com/NERC-CEH/catena) and xarray read as-is.

Each provider is a subpackage with up to three layers:

- **fetch** downloads raw files and records where and when they came from;
- **standardise** converts them to netCDF with named dims, CF units and provenance attributes;
- **nodes** (some providers) are contract-annotated functions for preparation specific to the source, which catena finds by section name.

None of them needs catena, so the package is just as useful for getting data into xarray.

## Providers

| Provider | Extra | Credentials | |
|---|---|---|---|
| COSMOS-UK soil moisture and meteorology | `cosmos` | None | [COSMOS-UK](providers/cosmos-uk/index.md) |
| FLUXNET daily fluxes and meteorology, from the ICOS Carbon Portal | `fluxnet` | None | [FLUXNET](providers/fluxnet/index.md) |

## Installation

```sh
pip install "xharvest[cosmos] @ git+https://github.com/NERC-CEH/xharvest"
```

See [Getting started](getting-started.md) for a first download.
Each provider's overview covers downloading and standardising its data, with further pages on what the data mean, how standardisation works, catena and the API; [Adding a connector](adding-a-connector.md) covers adding a provider.
