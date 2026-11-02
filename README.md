# conduit-data

Data connectors for conduit

## Installation

```sh
pip install git+https://github.com/NERC-CEH/conduit-data
```

## Usage

```python
from conduit_data import greet

greet("world")
```

See the [documentation](https://nerc-ceh.github.io/conduit-data)
for more.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `uv sync`, then `just`.

```
just                  # lint, typecheck, test, check-examples, docs
just lint             # ruff format, marimo check --fix, ruff check --fix, marimo --strict
just lint-check       # non-mutating variant, used by CI
just check-canonical  # assert the notebooks are in marimo's canonical form
just check-examples   # actually execute the example notebooks
just typecheck        # pyright
just test             # pytest
just test-cov         # pytest with coverage, fails under 90%
just doctest          # run the doctest examples in src/
just docs             # export example notebooks, then zensical build
just docs-serve       # the same, with a live-reloading local server
```

---

Generated from a [Copier](https://copier.readthedocs.io/) template, recorded in
`.copier-answers.yml`. Pull later template changes with `copier update`.
