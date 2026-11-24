# COSMOS-UK

[COSMOS-UK](https://cosmos.ceh.ac.uk) is the UK Centre for Ecology & Hydrology's network of cosmic-ray soil moisture sites, with co-located meteorological and soil measurements.
`xharvest.cosmos` downloads site data from the [COSMOS-UK API](https://cosmos-api.ceh.ac.uk) and standardises it for catena and xarray.

| | |
|---|---|
| Install | `pip install "xharvest[cosmos] @ git+https://github.com/NERC-CEH/xharvest"` |
| Credentials | None |
| Licence | [Open Government Licence v3](http://www.nationalarchives.gov.uk/doc/open-government-licence), as stated by the API |
| Cite | [EIDC release](https://doi.org/10.5285/dde10e2b-ee1a-4b2b-a247-176db2f7bb31) (see [Citing the data](#citing-the-data)) |
| Resolution | Daily only |
| catena section | `[cosmos]` |

!!! warning "Daily data only"

    The API also serves 30-minute data, which xharvest does not fetch or standardise yet ([#8](https://github.com/NERC-CEH/xharvest/issues/8)).

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

## Standardise

```python
cosmos.to_netcdf(raw, "data/cosmos.nc")
```

```sh
xharvest cosmos standardise data/raw/*_1D_*.json --out data/cosmos.nc
```

Sidecars among the paths are skipped, so a glob over the download directory works.
Files from separate periods can be joined, such as January 2025 and January 2026, and the gap between them stays a gap: `time` holds only what was fetched, rather than NaN for the months nobody asked for.
A node that depends on regular spacing declares `Freq`, and raises on such a file.

The result has dims `(time, site)`:

| Name | Kind | Notes |
|---|---|---|
| `time` | dim | UTC, as naive `datetime64` |
| `site` | dim | Site identifier, e.g. `ALIC1` |
| `site_name` | coord on `site` | e.g. `Alice Holt` |
| `lat`, `lon` | coord on `site` | Degrees north and east |
| `altitude` | coord on `site` | The API's `z`, in metres (EPSG:5703) |
| `time_bounds` | coord on `(time, nv)` | The period each value covers |
| one per parameter, [listed below](#variables) | data, on `(time, site)` | `units`, `long_name`, `description` and `cell_methods` from the API |

- Values and units are the API's own, e.g. volumetric water content in `%`.
- Missing values become NaN, including outside a site's record and for sensors a site lacks, so every site has the same variables.
- Global attributes record provenance: `institution`, `source`, `license` and `history`.
- Nothing converts units, fills gaps, or removes values; [How standardisation works](standardise.md) shows every step.

### Variables

`fetch` requests every parameter below unless `parameters` (`--parameter`) names some.
A site without a parameter's sensor has NaN for it.
Names, units, aggregation methods and descriptions are the API's own, drawn from the site list in the test fixtures, so the table changes only when the fixtures are regenerated.

--8<-- "docs/providers/_variables/cosmos.md"

## Citing the data

The API serves live data with no DOI.
For published work, cite the most recent quality-controlled release on the EIDC, for example:

> Stanley, S., et al. (2026). Daily and sub-daily hydrometeorological and soil moisture data (2013-2025) [COSMOS-UK]. NERC EDS Environmental Information Data Centre. <https://doi.org/10.5285/dde10e2b-ee1a-4b2b-a247-176db2f7bb31>

## More

- [About the data](data.md): what a timestamp covers, snow days, and what the API leaves out, as checked against the data.
- [How standardisation works](standardise.md): every step from the downloaded files to the netCDF, and the judgement calls xharvest makes.
- [Using with catena](catena.md): contract types and the `[cosmos]` nodes.
- [Reference](reference.md): the CLI and the Python API.
