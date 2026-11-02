# Contributing

Contributions are welcome.
Please open a Pull Request against the `main` branch.

## Getting started

This project uses [`uv`](https://docs.astral.sh/uv/). 
Install the project and its development dependencies with

```sh
uv sync
```

A [`justfile`](justfile) provides the common tasks. Run everything with

```sh
just
```

or individually:

| Command | What it does |
|---|---|
| `just lint` | `ruff format`, `marimo check --fix`, `ruff check --fix`, `marimo check --strict` |
| `just lint-check` | Non-mutating variant, used by CI |
| `just check-canonical` | Asserts the example notebooks are in marimo's canonical form |
| `just check-examples` | Runs the example notebooks — the only step that executes cells |
| `just typecheck` | `pyright` |
| `just test` | `pytest` |
| `just test-cov` | `pytest` with coverage, failing under 90% |
| `just doctest` | Run the doctest examples in `src/` |
| `just docs` | Export the example notebooks, then `zensical build` |
| `just docs-serve` | The same, with a live-reloading local server |

If you don't have `just` on your PATH, prefix with `uv run`, e.g. `uv run just test`.

Consider installing [`pre-commit`](https://pre-commit.com/) so that the hooks in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) run before each commit:

```sh
uv tool install pre-commit
pre-commit install
```

## Documentation

The documentation is built with [Zensical](https://zensical.org/) from the Markdown in `docs/`, plus an API reference generated from docstrings by [mkdocstrings](https://mkdocstrings.github.io/).

`docs/example.md` is **generated** — it is exported from `examples/notebook.py` (a [marimo](https://marimo.io/) notebook) by `just docs`, with cell outputs rendered.
Edit the notebook, not the Markdown:

```sh
marimo edit examples/notebook.py
```

Preview the site locally with `just docs-serve`.

## Writing a connector

Each provider is a subpackage of `conduit_data`; `conduit_data.cosmos` is the reference.
[ADR 1](docs/adr/0001-scope-and-design.md) explains why the package is shaped this way.

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
The page states the extra, the credentials needed, the licence and how to cite the data, the standardised output's variables and coordinates, what a timestamp means, and anything the provider's data does not say about itself.

## Style

- Ruff enforces formatting and lint; see `[tool.ruff]` in `pyproject.toml`.
- Public functions and classes in `src/` need docstrings, in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Type annotations are expected; `pyright` runs over `src/` and `tests/`.
