# COSMOS-UK

[COSMOS-UK](https://cosmos.ceh.ac.uk) is the UK Centre for Ecology & Hydrology's network of cosmic-ray soil moisture sites, with co-located meteorological and soil measurements.
`xharvest.cosmos` downloads site data from the [COSMOS-UK API](https://cosmos-api.ceh.ac.uk) and standardises it for conduit and xarray.

| | |
|---|---|
| Install | `pip install xharvest[cosmos]` |
| Credentials | None |
| Licence | [Open Government Licence v3](http://www.nationalarchives.gov.uk/doc/open-government-licence), as stated by the API |
| Cite | [EIDC release](https://doi.org/10.5285/dde10e2b-ee1a-4b2b-a247-176db2f7bb31) (see [Citing the data](#citing-the-data)) |
| Collections | `1D` (daily), `30M` (30-minute) |
| conduit section | `[cosmos]` |

## Download

```python
from datetime import date
from xharvest import cosmos

cosmos.sites()  # identifiers, names, locations and periods of record
raw = cosmos.fetch(["ALIC1", "MOORH"], date(2025, 1, 1), date(2025, 3, 31), "data/raw")
```

or from the command line:

```sh
xharvest cosmos sites
xharvest cosmos fetch ALIC1 MOORH --start 2025-01-01 --end 2025-03-31 --out data/raw
```

- `fetch` writes one CoverageJSON file per site, with a `.meta.json` provenance sidecar.
- A file that already holds the same request is skipped; pass `overwrite=True` (`--overwrite`) to download again.
- `start` and `end` are both included; dates select whole GMT days.
- `parameters=[...]` (`--parameter`, repeated) requests only some parameters.
- 30-minute data is about 48 times the size of daily data, and `fetch` makes one request per site, so fetch long 30-minute records in pieces; `standardise` joins them.

## Standardise

```python
cosmos.to_netcdf(raw, "data/cosmos.nc")
```

```sh
xharvest cosmos standardise data/raw/*_1D_*.json --out data/cosmos.nc
```

Sidecars among the paths are skipped, so a glob over the download directory works.
Standardise each collection into its own file.

The result has dims `(time, site)`:

| Name | Kind | Notes |
|---|---|---|
| `time` | dim | UTC, as naive `datetime64` |
| `site` | dim | Site identifier, e.g. `ALIC1` |
| `site_name` | coord on `site` | e.g. `Alice Holt` |
| `lat`, `lon` | coord on `site` | Degrees north and east |
| `altitude` | coord on `site` | The API's `z`, in metres (EPSG:5703) |
| `time_bounds` | coord on `(time, nv)` | The period each value covers |
| one per parameter | data, on `(time, site)` | `units`, `long_name`, `description` and `cell_methods` from the API |

- Values and units are the API's own, e.g. volumetric water content in `%`.
- Missing values become NaN, including outside a site's record and for sensors a site lacks, so every site has the same variables.
- Global attributes record provenance: `institution`, `source`, `license` and `history`.

## About the data

### Timestamps

A **daily** value stamped `2025-01-01T00:00` covers the GMT day 2025-01-01.
A **30-minute** value covers the 30 minutes *ending* at its stamp, so `12:30` covers `12:00`–`12:30`.
Under this reading, the 30-minute precipitation summed over each day matches the daily totals to within rounding.

### Snow days

When there is snow on the ground the neutron counts no longer reflect soil moisture alone.
On those days (`snow == 1`), COSMOS-UK reports a `cosmos_vwc` estimated from the counts before the snow, which shows up as a constant run of values.
Use the [`cosmos_vwc_snow_masked`](#xharvest.cosmos.nodes.cosmos_vwc_snow_masked) node to drop them.

### What the API does not provide

The EIDC release of the same data has per-value flags (missing, infilled, estimated, unchecked) and quality-control flags.
The API has neither, so a value from the API may be infilled or estimated without saying so.

## Citing the data

The API serves live data with no DOI.
For published work, cite the most recent quality-controlled release on the EIDC, for example:

> Stanley, S., et al. (2026). Daily and sub-daily hydrometeorological and soil moisture data (2013-2025) [COSMOS-UK]. NERC EDS Environmental Information Data Centre. <https://doi.org/10.5285/dde10e2b-ee1a-4b2b-a247-176db2f7bb31>

## CLI

::: mkdocs-typer2
    :module: xharvest.cli.app
    :name: xharvest
    :command: cosmos
    :termynal: true
    :width: 80
    :prompt: ❯

Run `xharvest cosmos <command> --help` for a command's options; they mirror the Python API below.

## Python API

::: xharvest.cosmos.sites
    options:
      heading_level: 3

::: xharvest.cosmos.Site
    options:
      heading_level: 3

::: xharvest.cosmos.fetch
    options:
      heading_level: 3

::: xharvest.cosmos.Collection
    options:
      heading_level: 3

::: xharvest.cosmos.standardise
    options:
      heading_level: 3

::: xharvest.cosmos.to_netcdf
    options:
      heading_level: 3

## Conduit nodes

conduit finds these nodes under the config section `[cosmos]` once xharvest is installed.
They name their inputs after the standardised variables, so read the standardised file with `suffix = ""`:

```toml
[inputs.cosmos]
path = "data/cosmos.nc"
suffix = ""
vars = ["cosmos_vwc", "snow"]

[cosmos]
```

::: xharvest.cosmos.nodes.cosmos_vwc_snow_masked
    options:
      heading_level: 3
