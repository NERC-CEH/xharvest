# xharvest

Download environmental data from its providers, and standardise it into netCDF that [catena](https://github.com/NERC-CEH/catena) and xarray read as-is.

| Provider | Extra | Credentials |
|---|---|---|
| COSMOS-UK soil moisture and meteorology | `cosmos` | None |

## Installation

```sh
pip install "xharvest[cosmos] @ git+https://github.com/NERC-CEH/xharvest"
```

## Usage

```python
from datetime import date
from xharvest import cosmos

raw = cosmos.fetch("ALIC1", date(2025, 1, 1), date(2025, 1, 14), "data/raw")
cosmos.to_netcdf(raw, "data/cosmos.nc")
```

See the [documentation](https://nerc-ceh.github.io/xharvest) for more.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: `uv sync`, then `just`.

```
just                  # lint, typecheck, test, docs
just lint             # ruff format, ruff check --fix
just lint-check       # non-mutating variant, used by CI
just typecheck        # pyright
just test             # pytest
just test-cov         # pytest with coverage, fails under 90%
just test-live        # only the tests that call real provider APIs
just doctest          # run the doctest examples in src/
just docs             # zensical build
just docs-serve       # the same, with a live-reloading local server
```

---

Generated from a [Copier](https://copier.readthedocs.io/) template, recorded in
`.copier-answers.yml`. Pull later template changes with `copier update`.
