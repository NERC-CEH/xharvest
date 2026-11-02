# Contributing

Contributions are welcome.
Please open a Pull Request against the `main` branch.

- To add a provider, read [Adding a connector](docs/developers/adding-a-connector.md) first: it starts with opening an issue.
- [`docs/adr/`](docs/adr/) records the design decisions and why they were made; read them before proposing a change to the package's shape.
- xharvest is alpha, with no external users: make breaking changes rather than adding compatibility shims.

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
| `just lint` | `ruff format`, then `ruff check --fix` |
| `just lint-check` | Non-mutating variant, used by CI |
| `just typecheck` | `pyright` |
| `just test` | `pytest`, leaving out tests that call real APIs |
| `just test-live` | Only the tests that call real APIs |
| `just test-cov` | `pytest` with coverage, failing under 90% |
| `just doctest` | Run the doctest examples in `src/` |
| `just docs` | `zensical build` |
| `just docs-serve` | The same, with a live-reloading local server |

If you don't have `just` on your PATH, prefix with `uv run`, e.g. `uv run just test`.

Consider installing [`pre-commit`](https://pre-commit.com/) so that the hooks in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) run before each commit:

```sh
uv tool install pre-commit
pre-commit install
```

## Dependencies and tooling

- Tool versions are pinned in three places that must stay in step: `[dependency-groups] dev` in `pyproject.toml`, the revs in `.pre-commit-config.yaml`, and the `uv_build` bound in `[build-system]`.
- conduit is pinned to a commit in `[tool.uv.sources]`; move the pin deliberately, in its own commit.
- The project was generated from a [copier template](https://github.com/jmarshrossney/python-package-template).
  Never hand-edit `.copier-answers.yml`: to change an answer, run `copier update --vcs-ref <current _commit> --data key=value`, then resolve every conflict to the project's side.

## Documentation

The documentation is built with [Zensical](https://zensical.org/) from the Markdown in `docs/`.
Provider pages generate their Python API reference from docstrings with [mkdocstrings](https://mkdocstrings.github.io/), and their CLI reference from the typer app with [mkdocs-typer2](https://github.com/syn54x/mkdocs-typer2).
`docs/adr/` is excluded from the build; the ADRs are read on GitHub.

Preview the site locally with `just docs-serve`.

## Style

- Ruff enforces formatting and lint; see `[tool.ruff]` in `pyproject.toml`.
- Public functions and classes in `src/` need docstrings, in [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Type annotations are expected; `pyright` runs over `src/` and `tests/`.
