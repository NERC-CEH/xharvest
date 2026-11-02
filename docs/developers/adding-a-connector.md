# Adding a connector

A connector downloads one provider's data, standardises it, and optionally provides conduit nodes for preparing it.
Adding one is a proposal, then a pull request.

## Propose it

Open an issue on [NERC-CEH/xharvest](https://github.com/NERC-CEH/xharvest/issues) before writing code, saying:

- **the provider and data**: the service, the datasets or variables, and who will use them;
- **the licence**: whether it allows committing a few days of raw output as a test fixture, which every connector needs;
- **access**: whether downloads need an account, an API key or a licence acceptance;
- **dependencies**: the client library, if any, and what it pulls in (GDAL, for example, affects everyone, because every extra resolves in one lockfile);
- **the raw format**, and how far it is from netCDF with CF units;
- **source-specific preparation**: fill values, scale factors, QC flags, de-accumulation, or anything else every user would otherwise redo.

A provider whose licence forbids committing fixtures, or whose client library will not resolve alongside the others, is better served by a separate package.

## Write it

Each provider is a subpackage of `xharvest`; `xharvest.cosmos` is the reference.
[Design decisions](decisions.md) explains why the package is shaped this way.

| Module | What it does | May import |
|---|---|---|
| `_fetch.py` | `fetch(...) -> list[Path]`: downloads raw files to a directory, skipping any already present. | The provider's client library, through `require` |
| `_standardise.py` | `standardise(paths) -> xr.Dataset`, and `to_netcdf(paths, out)`. | xarray |
| `nodes.py` (optional) | Contract-annotated node functions for source-specific preparation, registered in the `conduit.modules` entry-point group. | `xarray-annotated`, `hamilton` |

The subpackage's `__init__.py` re-exports the public functions and types, and lists them in `__all__`; that list is the public API, and the provider page documents each name in it.
No module imports `conduit`, and `_fetch.py` and `_standardise.py` import neither `xarray-annotated` nor `hamilton`; `tests/test_layout.py` checks both.
The CLI command group in `cli/` calls these functions and adds nothing the Python API cannot do.

### Dependencies

The provider's third-party dependencies go in an extra named after the subpackage, and in `all`.
Import them with `xharvest._extras.require(module, extra)`, inside the function that needs them, so the subpackage imports without them and the error names the extra.
`tests/test_layout.py` rejects a module-level import of an extra's package.

### Provenance

Raw provider files rarely record where or when they were downloaded, so `fetch` writes every file with `xharvest.provenance.save`, which writes a sidecar beside it, and `standardise` reads the sidecars back.
`save` writes both files atomically, sidecar last, so a file without a sidecar is from an interrupted download.
`fetch` skips a file only if `provenance.is_fetched` says it holds the same request; that raises if the file holds a different one.
A sidecar's `metadata` also holds anything standardisation needs that the raw file omits, such as COSMOS-UK site names.
The standardised dataset carries the global attributes in `provenance.PROVENANCE_ATTRS`: `institution`, `source`, `license`, and `history`, with one line per download (`provenance.history_line`) and one for the standardisation.

### Standardised output

netCDF with:

- named dimensions, and at most one time dimension, whose coordinate is `datetime64`, in UTC;
- a `time_bounds` coordinate (`time` carries `bounds = "time_bounds"`) whenever values aggregate over a period, because providers differ on whether a stamp marks its period's start or end;
- fill values decoded to NaN, and scale factors applied, but units left as the provider gives them: unit conversion is conduit's job;
- a CF `units` attribute on every data variable, valid under `xarray_annotated.units.use_cf_units()`, and `cell_methods` where the provider says how values were aggregated;
- the provenance attributes above.

Raise `xharvest.errors.ProviderError` when a provider cannot be reached, rejects a request, or returns something the connector cannot read, with the provider's own message where it gives one.
Catch the client library's transport errors (for httpx, `httpx.TransportError`, which includes timeouts) and re-raise them as `ProviderError`, so callers and the CLI handle one exception.

### Tests

Tests must not touch the network or need credentials.

- Commit a few days of real raw output under `tests/fixtures/<provider>/`, trimmed to what the tests need, with a `make_fixtures.py` that regenerates it.
- Let `fetch` accept a client (as `cosmos.fetch` takes an `httpx.Client`), and test it against a mock transport serving the fixtures.
- Add the connector to `CONNECTORS` in `tests/test_contracts.py`, which checks the standardised output and the node contracts; a test fails until you do.
- Put tests that call the real API in `test_<provider>_live.py`, marked `live`; `just test-live` runs them.

### Docs

Add a page under `docs/providers/`, to the `zensical.toml` nav, and to the provider tables in `README.md` and `docs/index.md`.
Model it on [COSMOS-UK](../providers/cosmos-uk.md), with sections in this order:

1. an overview table: install, credentials, licence, how to cite, and the conduit section name;
2. download;
3. standardise, describing the output;
4. about the data: what a timestamp means, and the provider's quirks and gaps;
5. citing the data;
6. the CLI reference: the command group's help, then a heading and a mkdocs-typer2 block per command;
7. the Python API reference: one mkdocstrings block per name in `__all__`, in reading order;
8. conduit nodes, if there is a `nodes.py`: how conduit reads the output, then one mkdocstrings block per node.

## Before opening the pull request

- [ ] `uv run just` passes, and `uv run just test-live` passes against the real API.
- [ ] The provider page is in the nav and the provider tables.
- [ ] Anything this connector settled that the next one should follow is added to this page.

## Shared API

::: xharvest.provenance
    options:
      heading_level: 3

::: xharvest.errors
    options:
      heading_level: 3

::: xharvest._extras.require
    options:
      heading_level: 3
