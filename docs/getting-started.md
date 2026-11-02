# Getting started

## Installation

Each provider's dependencies sit behind an install extra named after it:

```sh
pip install "xharvest[cosmos] @ git+https://github.com/NERC-CEH/xharvest"
```

`all` installs every extra.
With [uv](https://docs.astral.sh/uv/):

```sh
uv add "xharvest[all] @ git+https://github.com/NERC-CEH/xharvest"
```

## A first download

Fetch two weeks of daily COSMOS-UK data for one site, and standardise it:

```python
from datetime import date
from xharvest import cosmos

raw = cosmos.fetch("ALIC1", date(2025, 1, 1), date(2025, 1, 14), "data/raw")
ds = cosmos.standardise(raw)
cosmos.to_netcdf(raw, "data/cosmos.nc")
```

The same from the command line:

```sh
xharvest cosmos fetch ALIC1 --start 2025-01-01 --end 2025-01-14 --out data/raw
xharvest cosmos standardise data/raw/*.json --out data/cosmos.nc
```

`data/cosmos.nc` is ready for a conduit `[inputs.*]` section.
Each provider's page says what its standardised output contains and which conduit nodes it provides; start with [COSMOS-UK](providers/cosmos-uk.md).
