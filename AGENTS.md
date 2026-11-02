# AGENTS.md

## Project overview

`xharvest` — harvests environmental data from many providers into standardised, xarray-ready netCDF, for xarray and conduit.
`docs/adr/` says why the package is shaped as it is, and `docs/developers/adding-a-connector.md` holds the rules a connector follows.
`tests/test_layout.py` and `tests/test_contracts.py` enforce most of them.

## Source layout

```
src/xharvest/
  __init__.py      — package docstring and version
  _extras.py       — `require`: lazy import naming the install extra
  errors.py        — ProviderError
  provenance.py    — fetch sidecars, and the provenance attributes they become
  cosmos/          — COSMOS-UK: fetch.py, standardise.py, nodes.py
  cli/             — `xharvest` (typer); commands only call the library
tests/
  fixtures/<provider>/  — trimmed real responses, with the make_fixtures.py that regenerates them
  test_contracts.py     — the shared harness every connector is added to
  test_layout.py        — import rules
docs/
  providers/       — one page per provider: usage, then generated Python API and CLI references
  developers/      — adding a connector; decisions.md includes every ADR in adr/
  adr/             — architecture decision records, excluded from the build as pages of their own
site/              — built documentation output (gitignored)
```

- Tests never touch the network. Tests marked `live` call real APIs and run only with `just test-live`.
- `conduit` is a test dependency only, pinned to a commit in `[tool.uv.sources]`; no module in `src/` may import it.

## Commands

All via `just`; prefix with `uv run` if `just` isn't on the PATH.

| Command | What it does |
|---|---|
| `just` | lint → typecheck → test → docs, in order |
| `just lint` | `ruff format` + `ruff check --fix` |
| `just lint-check` | Non-mutating variant for CI |
| `just typecheck` | `pyright` |
| `just test` | `pytest` |
| `just test-live` | Only the tests that call real provider APIs |
| `just test-cov` | `pytest` with coverage, `--cov-fail-under=90` |
| `just doctest` | Doctests in `src/` |
| `just docs` | `zensical build` |

Setup: `uv sync`.

## Toolchain

uv (packaging), just (tasks), ruff (format + lint), pyright (types), pytest (tests), zensical + mkdocstrings + mkdocs-typer2 (docs), pre-commit, GitHub Actions.

## Conventions

- Ruff `select` is explicit, never left to defaults — see the comment in `pyproject.toml`.
- Docstrings are required in `src/` (google convention) and exempt in `tests/`. They render into the provider pages.
- Tool versions are pinned in three places that must stay in step: `[dependency-groups] dev`, `.pre-commit-config.yaml` revs, and the `uv_build` bound in `[build-system]`.

## This project was generated from a template

The answers are in `.copier-answers.yml`. `copier update` pulls later template
changes in; it uses that file to replay the original answers, so keep it
committed and don't hand-edit it.
