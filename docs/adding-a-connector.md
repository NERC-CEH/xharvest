# Adding a connector

A connector downloads one provider's data, standardises it, declares what the standardised variables look like, and optionally provides catena nodes for preparing it.
Adding one is a proposal, then a pull request.
[CONTRIBUTING.md](https://github.com/NERC-CEH/xharvest/blob/main/CONTRIBUTING.md) covers what applies to every contribution: setting up, running the checks, and keeping pinned tools in step.

## Propose it

Open an issue on [NERC-CEH/xharvest](https://github.com/NERC-CEH/xharvest/issues) before writing code, covering:

- **provider and data**: the service, datasets or variables, and who will use them;
- **licence**: does it allow committing a few days of raw output as a test fixture?
- **access**: account, API key or licence acceptance;
- **dependencies**: the client library and what it pulls in (GDAL, say, affects everyone, since all extras share one lockfile);
- **raw format**, and how far it is from netCDF with CF units;
- **source-specific preparation**: fill values, scale factors, QC flags, de-accumulation.

A provider whose licence forbids committing fixtures, or whose client library will not resolve alongside the others, is better served by a separate package.

## Write it

Each provider is a subpackage of `xharvest`; `xharvest.cosmos` is the reference.
The [design decisions](https://github.com/NERC-CEH/xharvest/tree/main/docs/adr) explain why the package is shaped this way.

| Module | What it does | May import |
|---|---|---|
| `_fetch.py` | `fetch(...) -> list[Path]`: downloads raw files to a directory, skipping any already present. | The provider's client library, through `require` |
| `_pipeline.py` | The nodes of the standardisation graph (see below). | xarray, `hamilton` |
| `_standardise.py` | `standardise(paths) -> xr.Dataset`, which runs the graph, and `to_netcdf(paths, out)`. | xarray |
| `_variables.py` | One contract type per standardised variable, and `VARIABLES`, mapping each variable's name to its type. | `xarray-annotated` |
| `nodes.py` (optional) | Contract-annotated node functions for source-specific preparation, registered in the `catena.modules` entry-point group. | `xarray-annotated`, `hamilton` |

- `__init__.py` lists the public API in `__all__`; the provider page documents each name in it.
- The CLI command group in `cli/` calls these functions and adds nothing the Python API cannot do.
- `tests/test_layout.py` enforces the import rules in the table.
- A reader for a file format several providers share goes in a private top-level module of nodes, as `xharvest._fluxnet` does for FLUXNET archives, so each provider's graph reuses it.

### Standardisation graph

`standardise` runs a Hamilton graph built from `_pipeline.py` and any shared format module, from one input, `paths`, to one output, `dataset`, so a reader can see each thing done to the provider's data.
[ADR 2](https://github.com/NERC-CEH/xharvest/blob/main/docs/adr/0002-standardise-as-hamilton-graph.md) gives the reasons; `xharvest.icos` is the reference until COSMOS-UK is converted.

- One node does one thing, to every site and variable at once: never a node per site or per variable, and no dynamic fan-out.
- Every node has a docstring saying what it does and why, and an `action` tag from `xharvest._graph.ACTIONS`.
  Tag a decision the provider does not state `interprets`, so it stands out in the graph.
- A `checks` node returns what it checked, and the nodes after it take that, since Hamilton runs only the nodes the output needs.
- Helpers are private (`_name`), and only for mechanics within one node; any decision about the data is a node.
- Run the graph with `xharvest._graph.run`, which keeps Hamilton's error logging quiet and raises the node's exception unchanged.
- Add the graph to `GRAPHS` in `tests/test_graph.py`, which checks the rules above, and in `scripts/render_graphs.py`, which draws it for the docs.
- Never register a pipeline module in `catena.modules`.

### Dependencies

The provider's third-party dependencies go in an extra named after the subpackage, and in `all`.
Import them inside the function that needs them, with `xharvest._extras.require`, so the subpackage imports without them.

### Provenance

Standardisation cannot recover where or when a raw file came from, so capture it at fetch time:

- write every raw file with `xharvest.provenance.save`, and skip a download only if `provenance.is_fetched` says so;
- put anything else `standardise` needs that the raw file omits, such as COSMOS-UK site names, in the sidecar's `metadata`;
- give the standardised dataset the global attributes in `provenance.PROVENANCE_ATTRS`.

### Standardised output

netCDF with:

- named dimensions, and at most one time dimension, whose coordinate is `datetime64`, in UTC;
- a `time_bounds` coordinate (`time` carries `bounds = "time_bounds"`) whenever values aggregate over a period, because providers differ on whether a stamp marks its period's start or end;
- fill values decoded to NaN, and scale factors applied, but units left as the provider gives them: unit conversion is the consuming node's job;
- a CF `units` attribute on every data variable, valid under `xarray_annotated.units.use_cf_units()`, and `cell_methods` where the provider says how values were aggregated;
- a provider's unit string that is not valid CF rewritten as the same unit in CF (`deg C` as `degC`), with the original kept in a `provider_units` attribute: this is renaming, not conversion, and a string with no known CF equivalent raises `ProviderError` rather than passing through;
- the provenance attributes above.

### Contract types

`_variables.py` is the single source of truth for what the standardised variables look like, to catena and to anyone writing a node.
Each type is `Annotated[xr.DataArray, ...]` with the provider's `Unit` and the `Coords` every variable carries.
Types with the same unit and coordinates are the same object, since `typing.Annotated` treats equal metadata as equal types, so a name documents intent but does not tell variables apart; `VARIABLES` is what pairs each variable with its contract.
Name a type after its quantity without a provider prefix (`Precip`, not `CosmosPrecip`); users write `cosmos.Precip`, so the module keeps providers apart.
Declare `Dims` only if no reasonable selection removes one, and leave `Freq` to consumers unless the provider fixes it.
Nodes annotate their inputs with these types, and so can users, adding facets with `Annotated[Type, Freq("D")]`.
`tests/test_contracts.py` checks that `VARIABLES` covers every standardised variable, that the fixtures meet it, and that no node input contradicts it.

### Nodes

Name a node's data parameters after the standardised variables they read, and give the node a name that carries the provider, as `cosmos_vwc_snow_masked` does.
Decorate every node with `xharvest._suffix.follows_suffix("<provider>_suffix")`, outermost, so a config can give the node and its inputs the suffix the input section uses; this is how two providers' files with a variable in common stay apart.
Make settings keyword-only; they keep their names.
`tests/test_contracts.py` fails for any node that does not take the suffix.

### Errors

- Raise `xharvest.errors.ProviderError` when a provider cannot be reached, rejects a request, or returns something unreadable, with the provider's own message where it gives one.
- Re-raise the client library's transport errors (e.g. `httpx.TransportError`) as `ProviderError`, so callers handle one exception.
- Where the provider publishes a checksum, verify each download against it and raise `ProviderError` on a mismatch, as `icos.fetch` does.

### Tests

Tests must not touch the network or need credentials.

- Commit a few days of real raw output under `tests/fixtures/<provider>/`, trimmed to what the tests need, with a `make_fixtures.py` that regenerates it.
  Never hand-edit fixtures.
  Regenerated data files should be byte-identical; if they are not, the provider has revised its data.
  Where the provider serves only large files, as ICOS serves whole-site archives, `make_fixtures.py` fetches one with the connector and writes a trimmed copy under the same name, keeping the real sidecar.
- Let `fetch` accept a client (as `cosmos.fetch` takes an `httpx.Client`), and test it against a mock transport serving the fixtures.
- Add the connector to `CONNECTORS` in `tests/test_contracts.py`, which checks the standardised output against `VARIABLES` and the node contracts against both; a test fails until you do.
- Put tests that call the real API in `test_<provider>_live.py`, marked `live`; `just test-live` runs them.
  Where practical, include the checks behind the provider page's claims about the data, so a new release re-checks them.

### Docs

Add a page under `docs/providers/`, to the `zensical.toml` nav, and to the provider tables in `README.md` and `docs/index.md`.
The page embeds the graph `just graphs` draws (`_graphs/<provider>.svg`) and renders the node reference from the graph's modules, in place of a hand-written list of what `standardise` does; see the [ICOS](providers/icos.md) page.
Copy the structure of the [COSMOS-UK](providers/cosmos-uk.md) page.
Its "About the data" section must say what a timestamp means.
Check claims like this against the data, not only the provider's docs, and record what was checked and how.
COSMOS-UK's timestamp convention, for example, was settled by summing 30-minute values into daily ones.

## Before opening the pull request

- [ ] `uv run just` passes, and `uv run just test-live` passes against the real API.
- [ ] The provider page is in the nav and the provider tables.
- [ ] Anything this connector settled that the next one should follow is added to this page.
