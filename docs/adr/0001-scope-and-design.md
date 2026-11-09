## 1. Data connectors live in a separate package that does not depend on catena

- **Status:** accepted
- **Date:** 2026-11-02

### Context

Applying [catena](https://github.com/NERC-CEH/catena) usually involves three steps:

1. **Download** data from a provider such as ICOS, SoilGrids, ECMWF/Copernicus or AppEEARS.
2. **Prepare** it, specifically for that source: decode fill values, apply scale factors, mask on QC flags, de-accumulate.
3. **Run** it through a pipeline of models and analyses.

catena covers step 3, and its inputs are files.
Downloading does not fit inside a catena pipeline, because it is network-bound, credentialed and non-deterministic.
A blocked or sharded run would contact the provider once per shard, and a cache would depend on remote state.

Preparation is the opposite: pure xarray transforms whose typical bugs are mistakes in units, dims or time frequency.
These are exactly what catena's whole-DAG contract check catches before compute.

### Decision

Connectors for each provider live in this package, separate from catena.
Each connector has up to three layers:

- **fetch** downloads raw files through a Python API, wrapped by a CLI.
- **standardise** converts them to netCDF or Zarr that catena reads as-is.
- **nodes** (optional) provide preparation steps as contract-annotated node functions.

No layer imports catena, so the package is useful to anyone who just wants the data.
catena finds the node modules through its `catena.modules` entry point when both are installed.
catena itself never downloads anything, and does not depend on this package.

### Consequences

- catena stays free of network access and credentials, and of provider APIs that change underneath it.
- Changes in provider APIs are absorbed here.
- Each provider's dependencies sit behind an extra (`pip install <package>[<provider>]`), and all extras must resolve together in one lockfile.
- One version covers every connector, so a fix for one provider releases them all.
