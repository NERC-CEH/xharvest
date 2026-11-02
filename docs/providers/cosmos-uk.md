# COSMOS-UK

[COSMOS-UK](https://cosmos.ceh.ac.uk) is the UK Centre for Ecology & Hydrology's network of cosmic-ray soil moisture sites, with co-located meteorological and soil measurements.
`conduit_data.cosmos` downloads site data from the [COSMOS-UK API](https://cosmos-api.ceh.ac.uk) and standardises it for conduit and xarray.

| | |
|---|---|
| Install | `pip install conduit-data[cosmos]` |
| Credentials | None |
| Licence | [Open Government Licence v3](http://www.nationalarchives.gov.uk/doc/open-government-licence), as stated by the API |
| Collections | `1D` (daily), `30M` (30-minute) |
| conduit section | `[cosmos]` |

## Download

```python
from datetime import date
from conduit_data import cosmos

cosmos.sites()  # identifiers, names, locations and periods of record
raw = cosmos.fetch(["ALIC1", "MOORH"], date(2025, 1, 1), date(2025, 3, 31), "data/raw")
```

or from the command line (needs the `cli` extra too):

```sh
conduit-data cosmos sites
conduit-data cosmos fetch ALIC1 MOORH --start 2025-01-01 --end 2025-03-31 --out data/raw
```

`fetch` writes one CoverageJSON file per site, named `{site}_{collection}_{start}_{end}.json`, with a `.meta.json` sidecar recording the request and when it was made.
It skips files that already exist; pass `overwrite=True` (`--overwrite`) to download again.
The interval is closed: both `start` and `end` are included.
Pass `parameters=[...]` (`--parameter`, repeated) to request only some parameters; the API lists the valid names if you give an invalid one.

The 30-minute collection is about 48 times the size of the daily one.
`fetch` makes one request per site whatever the range, so request long 30-minute records in pieces.

## Standardise

```python
cosmos.to_netcdf(raw, "data/cosmos.nc")
```

```sh
conduit-data cosmos standardise data/raw/*_1D_*.json --out data/cosmos.nc
```

Sidecars among the paths are skipped, so a glob over the download directory works.
Files from different collections cannot be combined; standardise each collection into its own file.

The result has dims `(time, site)`:

| Name | Kind | Notes |
|---|---|---|
| `time` | dim | UTC, as naive `datetime64` |
| `site` | dim | Site identifier, e.g. `ALIC1` |
| `lat`, `lon` | coord on `site` | Degrees north and east |
| `altitude` | coord on `site` | The API's `z`, in metres (EPSG:5703). It can differ from the altitude in the EIDC site metadata (Alice Holt: 80 m here, 74 m there). |
| `time_bounds` | coord on `(time, nv)` | The period each value covers |
| one per parameter | data, on `(time, site)` | `units`, `long_name`, `description` and `cell_methods` from the API |

Values are the API's own, in the API's units: volumetric water content is in `%`, radiation in `MJ m-2 day-1`.
Missing values become NaN.
Sites are outer-joined on time, so a site is NaN-padded outside its own record.
A parameter for a sensor a site does not have is kept, entirely NaN, so every site has the same variables.

The global attributes record provenance: `institution`, `source`, `license`, and a `history` line for each download and for the standardisation.

### Timestamps

A **daily** value stamped `2025-01-01T00:00` covers the GMT day 2025-01-01.
A **30-minute** value covers the 30 minutes *ending* at its stamp, so `12:30` covers `12:00`–`12:30`.
`time_bounds` records both.
Under this reading, the 30-minute precipitation summed over each day matches the daily totals to within rounding.

### Snow days

When there is snow on the ground the neutron counts no longer reflect soil moisture alone.
On those days (`snow == 1`), COSMOS-UK reports a `cosmos_vwc` estimated from the counts before the snow, which shows up as a constant run of values.
Use the `cosmos_vwc_snow_masked` node to drop them.

### What the API does not provide

The EIDC release of the same data has per-value flags (missing, infilled, estimated, unchecked) and quality-control flags.
The API has neither, so a value from the API may be infilled or estimated without saying so.

## Use in conduit

```toml
[inputs.cosmos]
path = "data/cosmos.nc"
suffix = ""
vars = ["cosmos_vwc", "snow"]

[cosmos]
```

`[cosmos]` provides:

| Node | Inputs | Output |
|---|---|---|
| `cosmos_vwc_snow_masked` | `cosmos_vwc` (`%`, daily), `snow` (`1`, daily) | `cosmos_vwc`, NaN on snow days (`%`, daily) |

The node names its inputs after the standardised variables, hence `suffix = ""`.
A node that needs VWC as a fraction declares `Unit("m3 m-3")` on its input, and conduit converts from percent.

## Citing the data

The API serves live data with no DOI.
For published work, cite the most recent quality-controlled release on the EIDC, for example:

> Stanley, S., et al. (2026). Daily and sub-daily hydrometeorological and soil moisture data (2013-2025) [COSMOS-UK]. NERC EDS Environmental Information Data Centre. <https://doi.org/10.5285/dde10e2b-ee1a-4b2b-a247-176db2f7bb31>
