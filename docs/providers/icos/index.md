# ICOS (ecosystem stations)

[ICOS](https://www.icos-cp.eu) ecosystem stations measure more than fluxes: their teams also sample leaf area, biomass, canopy height and soil properties, and the Ecosystem Thematic Centre (ETC) publishes these ancillary measurements in each station's ETC L2 archive on the ICOS Carbon Portal.
`xharvest.icos` downloads those archives and standardises the ancillary measurements for catena and xarray.
For the stations' fluxes and meteorology, use [FLUXNET](../fluxnet/index.md), which serves the FLUXNET release for ICOS and other networks alike.

| | |
|---|---|
| Install | `pip install "xharvest[icos] @ git+https://github.com/NERC-CEH/xharvest"` |
| Credentials | None |
| Licence | ICOS CC BY 4.0 data licence, as the portal states for each archive |
| Cite | One citation per station (see [Citing the data](#citing-the-data)) |
| Groups | LAI, biomass, canopy height, soil texture, soil stocks |
| catena nodes | None yet (see [Using with catena](catena.md)) |

Of the 93 stations with a current ETC L2 archive, 84 have ancillary measurements, but not all of every kind: 82 report LAI, 80 biomass, 54 soil texture and 31 soil stocks (see [Coverage](data.md#coverage)).
In the UK only UK-AMo is an ICOS ecosystem station, and it has no soil measurements.

The connector is a first implementation for research use, and takes shortcuts listed under [Limitations](#limitations).

## Download

```python
from xharvest import icos

icos.stations()  # station codes, names, locations, records and file names
raw = icos.fetch(["UK-AMo", "DE-Har"], "data/raw")
```

or from the command line:

```sh
xharvest icos stations
xharvest icos fetch UK-AMo DE-Har --out data/raw
```

- `fetch` downloads each station's whole archive (5-330 MB), which also holds its fluxes and meteorology, with a `.meta.json` provenance sidecar recording the archive's citation, licence and persistent identifier.
- Each download is checked against the SHA-256 the portal publishes.
- A station has one current archive: its final L2 archive, or the interim one, updated monthly, that supersedes it. Where the portal lists both as current, `stations` takes the one whose record ends later.
- Files keep the portal's name, e.g. `ICOSETC_UK-AMo_ARCHIVE_INTERIM_L2.zip`, which stays the same from one monthly version to the next. Once the portal has a newer version, fetching into the same directory raises until you pass `overwrite=True` (`--overwrite`).

## Standardise

`standardise` reads one group of measurements at a time, from any number of archives:

```python
lai = icos.standardise(raw, "LAI")
icos.to_netcdf(raw, "data/soil_tex.nc", "SOIL_TEX")
```

```sh
xharvest icos standardise data/raw/*.zip --group LAI --out data/lai.nc
```

`GROUPS` lists the groups and their value variables: `LAI`, `BIOMASS`, `HEIGHTC`, `SOIL_TEX` and `SOIL_STOCK`, the archive's BIF group names without `GRP_`.
Sidecars among the paths are skipped, so a glob over the download directory works.
An archive with no ancillary file raises.

Each measurement is one record, as the archive gives it.
Nothing is averaged, pivoted into time series, or classified, because the archive tells measurements of different things apart only by qualifiers that are partly free text (see [Telling records apart](data.md#telling-records-apart)).
Select records on the qualifiers instead:

```python
mean_gai = lai.where(
    (lai.LAI_TYPE == "GAI") & (lai.LAI_STATISTIC == "Mean") & (lai.LAI_SPP == ""),
    drop=True,
)
```

The result has one dim, `record`, over every station's records:

| Name | Kind | Notes |
|---|---|---|
| `record` | dim | One per measurement, with no coordinate |
| `site`, `site_name`, `lat`, `lon` | coord on `record` | The station, from the archive's site metadata |
| `time` | coord on `record` | The measurement's local date, as the archive gives it, not converted to UTC |
| `time_bounds` | coord on `(record, nv)` | The period the measurement's dates name (see [Dates](data.md#dates)) |
| Qualifiers, e.g. `LAI_TYPE`, `LAI_STATISTIC`, `SOIL_TEX_PROFILE_MIN` | coord on `record` | Every other variable the archive gives for the measurement: strings, empty where unset, or numbers for depths, counts and uncertainties, NaN where unset |
| [The group's value variables](#variables) | data on `record` | NaN where a record does not give one |

- Names and values are the archive's.
  Units come from the archive's variable dictionary, `BIF_Ancillary_Variables.csv`, renamed to CF with the original kept in `provider_units`: `%vol` is `%`, `g C m-2` is `g m-2`, `kgDM m-2` is `kg m-2`.
  What is weighed and what a percentage is of are in the `description`, not the unit.
- A qualifier one station gives and another does not is empty, or NaN, at the other's records, so every station has the same coordinates.
- Global attributes record provenance: `institution`, `source`, `license`, `history`, and every station's citation in `references`.
- Nothing converts units or interpolates between measurement dates; [How standardisation works](standardise.md) shows every step.

The test fixtures' LAI, from UK-AMo in 2023 and DE-Har, prints as:

--8<-- "docs/providers/_variables/icos-dataset.md"

### Variables

Units are the CF units `standardise` writes; descriptions are the archive's own, from its variable dictionary.

--8<-- "docs/providers/_variables/icos.md"

## Limitations

The first implementation takes these shortcuts:

- Records are not combined into `(time, site)` series, and their approaches are not classified: moss cover, for example, is reported as GAI ([#18](https://github.com/NERC-CEH/xharvest/issues/18)).
- Biomass in carbon (`gC m-2`, 101 of 17,273 records) is dropped, keeping dry matter only ([#19](https://github.com/NERC-CEH/xharvest/issues/19)).
- Biomass organs are free text and are not normalised: `total AG`, `Total AG` and `Total aboveground` are kept as written ([#20](https://github.com/NERC-CEH/xharvest/issues/20)).
- Only five groups are read; soil chemistry, litter, roots, tree counts and the rest are not ([#21](https://github.com/NERC-CEH/xharvest/issues/21)).
- `time` is the station's local date, not a UTC time ([#22](https://github.com/NERC-CEH/xharvest/issues/22)).
- The archive's fluxes, meteorology and FLUXNET files are not read; use [FLUXNET](../fluxnet/index.md) ([#23](https://github.com/NERC-CEH/xharvest/issues/23)).

## Citing the data

The licence requires a citation for every station used.
`fetch` records each archive's citation, as the portal gives it, in its sidecar, and `standardise` lists them in the `references` attribute, for example:

> Nemitz, E., Callaghan, N., Cash, J., Coyle, M., Coyle, M., Fincham, W., Grenier, M., Harvey, D., Helfter, C., Jones, M., Leeson, S., Levy, P., Mullinger, N., Ocallaghan, F., van Dijk, N., Vandome, E., Yeung, K. (2026). ETC L2 ARCHIVE from Auchencorth Moss, 2021-01-01–2026-08-31, ICOS RI, <https://hdl.handle.net/11676/M6gyVbSMpTn4eDb_usFEuYhN>

## More

- [About the data](data.md): coverage, how to tell records apart, dates, and units, as checked against the data.
- [How standardisation works](standardise.md): every step from the downloaded archives to the netCDF, and the judgement calls xharvest makes.
- [Using with catena](catena.md): contract types; there are no nodes yet.
- [Reference](reference.md): the CLI and the Python API.
