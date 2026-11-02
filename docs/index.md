# xharvest

Download environmental data from its providers, and standardise it into netCDF that [conduit](https://github.com/NERC-CEH/conduit) and xarray read as-is.

Each provider is a subpackage with up to three layers:

- **fetch** downloads raw files and records where and when they came from;
- **standardise** converts them to netCDF with named dims, CF units and provenance attributes;
- **nodes** (some providers) are contract-annotated functions for preparation specific to the source, which conduit finds by section name.

None of them needs conduit, so the package is just as useful for getting data into xarray.

## Providers

| Provider | Extra | Credentials | |
|---|---|---|---|
| COSMOS-UK soil moisture and meteorology | `cosmos` | None | [COSMOS-UK](providers/cosmos-uk.md) |

## Installation

```sh
pip install "xharvest[cosmos] @ git+https://github.com/NERC-CEH/xharvest"
```

See [Getting started](getting-started.md) for a first download.
Each provider page has its usage, Python API and CLI reference, and [Adding a connector](adding-a-connector.md) covers adding a provider.
