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

Each provider is a subpackage of `conduit_data`.
[ADR 1](docs/adr/0001-scope-and-design.md) explains why the package is shaped this way.

| Layer | What it does | May import |
|---|---|---|
| fetch | `fetch(...) -> list[Path]`: downloads raw files to a directory, skipping any already present. A CLI subcommand wraps it, and adds nothing the Python API cannot do. | The provider's client library |
| standardise | Converts raw files into the standardised output described below. | xarray |
| nodes (optional) | Contract-annotated node functions for source-specific preparation, registered in the `conduit.modules` entry-point group. | `xarray-annotated`, `hamilton` |

No module imports `conduit`.

Standardised output is netCDF or Zarr with:

- named dimensions, and at most one time dimension, whose coordinate is `datetime64` or cftime;
- fill values decoded to NaN, and scale factors applied;
- a CF `units` attribute on every data variable;
- provenance attributes on the dataset: provider, dataset identifier or DOI, licence, request parameters, retrieval time.

The provider's third-party dependencies go in an extra named after the subpackage, and in `all`.
Import them lazily, and raise an error naming the extra if they are missing.

Tests must not touch the network or need credentials.
Test the standardise layer against a small committed fixture of raw provider output.

## Style

- Ruff enforces formatting and lint; see `[tool.ruff]` in `pyproject.toml`.
- Public functions and classes in `src/` need docstrings, in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Type annotations are expected; `pyright` runs over `src/` and `tests/`.
