## 1. Data connectors live in a separate package that does not depend on conduit

- **Status:** accepted
- **Date:** 2026-11-02

### Context

Applying [conduit](https://github.com/NERC-CEH/conduit) usually involves three steps:

1. **Download** data from a provider such as ICOS, SoilGrids, ECMWF/Copernicus or AppEEARS.
2. **Prepare** it, specifically for that source: decode fill values, apply scale factors, mask on QC flags, de-accumulate.
3. **Run** it through a pipeline of models and analyses.

conduit covers step 3, and its inputs are files.
Downloading does not fit inside a conduit pipeline, because it is network-bound, credentialed and non-deterministic.
A blocked or sharded run would contact the provider once per shard, and a cache would depend on remote state.

Preparation is the opposite: pure xarray transforms whose typical bugs are mistakes in units, dims or time frequency.
These are exactly what conduit's whole-DAG contract check catches before compute.

### Decision

Connectors for each provider live in this package, separate from conduit.
Each connector has up to three layers:

- **fetch** downloads raw files through a Python API, wrapped by a CLI.
- **standardise** converts them to netCDF or Zarr that conduit reads as-is.
- **nodes** (optional) provide preparation steps as contract-annotated node functions.

No layer imports conduit, so the package is useful to anyone who just wants the data.
conduit finds the node modules through its `conduit.modules` entry point when both are installed.
conduit itself never downloads anything, and does not depend on this package.

### Consequences

- conduit stays free of network access and credentials, and of provider APIs that change underneath it.
- Changes in provider APIs are absorbed here.
- Each provider's dependencies sit behind an extra (`pip install <package>[<provider>]`), and all extras must resolve together in one lockfile.
- One version covers every connector, so a fix for one provider releases them all.
