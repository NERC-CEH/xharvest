# Adding a connector

A connector downloads one provider's data, standardises it, and optionally provides conduit nodes for preparing it.
Adding one is a proposal, then a pull request.

## Propose it

Open an issue on [NERC-CEH/conduit-data](https://github.com/NERC-CEH/conduit-data/issues) before writing code, saying:

- **the provider and data**: the service, the datasets or variables, and who will use them;
- **the licence**: whether it allows committing a few days of raw output as a test fixture, which every connector needs;
- **access**: whether downloads need an account, an API key or a licence acceptance;
- **dependencies**: the client library, if any, and what it pulls in (GDAL, for example, affects everyone, because every extra resolves in one lockfile);
- **the raw format**, and how far it is from netCDF with CF units;
- **source-specific preparation**: fill values, scale factors, QC flags, de-accumulation, or anything else every user would otherwise redo.

A provider whose licence forbids committing fixtures, or whose client library will not resolve alongside the others, is better served by a separate package.

## Write it

Each provider is a subpackage of `conduit_data`; `conduit_data.cosmos` is the reference.
[Design decisions](decisions.md) explains why the package is shaped this way.

| Module | What it does | May import |
|---|---|---|
| `fetch.py` | `fetch(...) -> list[Path]`: downloads raw files to a directory, skipping any already present. | The provider's client library, through `require` |
| `standardise.py` | `standardise(paths) -> xr.Dataset`, and `to_netcdf(paths, out)`. | xarray |
| `nodes.py` (optional) | Contract-annotated node functions for source-specific preparation, registered in the `conduit.modules` entry-point group. | `xarray-annotated`, `hamilton` |

No module imports `conduit`, and `fetch.py` and `standardise.py` import neither `xarray-annotated` nor `hamilton`; `tests/test_layout.py` checks both.
The CLI command group in `cli/` calls these functions and adds nothing the Python API cannot do.

### Dependencies

The provider's third-party dependencies go in an extra named after the subpackage, and in `all`.
Import them with `conduit_data._extras.require(module, extra)`, inside the function that needs them, so the subpackage imports without them and the error names the extra.
`tests/test_layout.py` rejects a module-level import of an extra's package.

### Provenance

Raw provider files rarely record where or when they were downloaded, so `fetch` calls `conduit_data.provenance.write_sidecar` for every file it writes, and `standardise` reads the sidecars back.
A sidecar's `metadata` also holds anything standardisation needs that the raw file omits, such as COSMOS-UK site names.
The standardised dataset carries the global attributes in `provenance.PROVENANCE_ATTRS`: `institution`, `source`, `license`, and `history`, with one line per download (`provenance.history_line`) and one for the standardisation.

### Standardised output

netCDF with:

- named dimensions, and at most one time dimension, whose coordinate is `datetime64`, in UTC;
- a `time_bounds` coordinate (`time` carries `bounds = "time_bounds"`) whenever values aggregate over a period, because providers differ on whether a stamp marks its period's start or end;
- fill values decoded to NaN, and scale factors applied, but units left as the provider gives them: unit conversion is conduit's job;
- a CF `units` attribute on every data variable, valid under `xarray_annotated.units.use_cf_units()`, and `cell_methods` where the provider says how values were aggregated;
- the provenance attributes above.

Raise `conduit_data.errors.ProviderError` when a provider rejects a request or returns something the connector cannot read, with the provider's own message where it gives one.

### Tests

Tests must not touch the network or need credentials.

- Commit a few days of real raw output under `tests/fixtures/<provider>/`, trimmed to what the tests need, with a `make_fixtures.py` that regenerates it.
- Let `fetch` accept a client (as `cosmos.fetch` takes an `httpx.Client`), and test it against a mock transport serving the fixtures.
- Add the connector to `CONNECTORS` in `tests/test_contracts.py`, which checks the standardised output and the node contracts.
- Put tests that call the real API in `test_<provider>_live.py`, marked `live`; `just test-live` runs them.

### Docs

Add a page under `docs/providers/`, to the `zensical.toml` nav, and to the provider tables in `README.md` and `docs/index.md`.
Model it on [COSMOS-UK](../providers/cosmos-uk.md): usage first, then the Python API and CLI references, generated with mkdocstrings and mkdocs-typer2.
The page states the extra, the credentials needed, the licence and how to cite the data, the standardised output's variables and coordinates, what a timestamp means, and anything the provider's data does not say about itself.

## Before opening the pull request

- [ ] `uv run just` passes, and `uv run just test-live` passes against the real API.
- [ ] The connector is in `CONNECTORS` in `tests/test_contracts.py`.
- [ ] The provider page is in the nav and the provider tables.
- [ ] Anything this connector settled that the next one should follow is added to this page.

## Shared API

::: conduit_data.provenance
    options:
      heading_level: 3

::: conduit_data.errors
    options:
      heading_level: 3

::: conduit_data._extras.require
    options:
      heading_level: 3
