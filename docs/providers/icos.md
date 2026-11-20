# ICOS Carbon Portal (FLUXNET)

The [ICOS Carbon Portal](https://www.icos-cp.eu) hosts the FLUXNET data product, eddy-covariance fluxes and meteorology processed with [ONEFlux](https://github.com/fluxnet/ONEFlux) v1.3, for several hundred sites.
`xharvest.icos` downloads it and standardises the daily files for catena and xarray.

| | |
|---|---|
| Install | `pip install xharvest[icos]` |
| Credentials | None |
| Licence | CC BY 4.0, as each archive's data policy states |
| Cite | One citation per site (see [Citing the data](#citing-the-data)) |
| Resolution | Daily only, for now |

The connector is partial ([#11](https://github.com/NERC-CEH/xharvest/issues/11)): daily files only, a fixed set of variables for soil moisture and ecosystem carbon modelling, tested on UK sites.
The archives come from several networks, not only ICOS: the first part of the file name says which (`ICOS`, `EUF` for the European Fluxes Database, `JPF`, `CNF`, `KOF`, `FLX`, `SAEON`).
In the UK only UK-AMo is an ICOS station; the other UK sites are `EUF`.

## Download

```python
from xharvest import icos

icos.sites()  # site codes, names, locations, records and file names
raw = icos.fetch(["UK-Cvn", "UK-AMo"], "data/raw")
```

or from the command line:

```sh
xharvest icos sites
xharvest icos fetch UK-Cvn UK-AMo --out data/raw
```

- `fetch` downloads each site's whole archive (20-250 MB), with a `.meta.json` provenance sidecar recording the archive's citation and persistent identifier.
- There is no date range: the portal serves whole-site archives only. Select a period after standardising.
- Each download is checked against the SHA-256 the portal publishes.
- Files keep the portal's name, e.g. `EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip`, so a new release arrives as a new file.
- An archive that already holds the same object is skipped; pass `overwrite=True` (`--overwrite`) to download again.

## Standardise

```python
icos.to_netcdf(raw, "data/icos.nc")
```

```sh
xharvest icos standardise data/raw/*.zip --out data/icos.nc
```

Sidecars among the paths are skipped, so a glob over the download directory works.
Sites whose data keep different local standard times (see [Timestamps](#timestamps)) cannot share a file, and raise; the UK sites are all UTC+0.

The result has dims `(time, site, depth)`:

| Name | Kind | Notes |
|---|---|---|
| `time` | dim | UTC start of the site's local standard day, as naive `datetime64` |
| `site` | dim | FLUXNET site code, e.g. `UK-Cvn` |
| `depth` | dim | Soil sensor depth, metres below ground, positive down |
| `site_name`, `lat`, `lon`, `altitude` | coord on `site` | From the archive's site metadata |
| `utc_offset`, `igbp`, `network` | coord on `site` | Hours from UTC to the data's clock; IGBP land cover; network code |
| `time_bounds` | coord on `(time, nv)` | The day each value covers |
| `SWC_F_MDS`, `TS_F_MDS` and their `_QC` | data, on `(time, site, depth)` | Soil water content and temperature profiles |
| the other variables below | data, on `(time, site)` | |

| Group | Variables |
|---|---|
| Meteorology | `TA_F`, `VPD_F`, `P_F`, `SW_IN_F`, `LW_IN_F`, `PA_F`, `WS_F`, `PPFD_IN`, `NETRAD`, `CO2_F_MDS` |
| Soil | `SWC_F_MDS`, `TS_F_MDS`, `G_F_MDS` |
| Energy and water | `LE_F_MDS`, `LE_CORR`, `LE_CORR_JOINTUNC`, `H_F_MDS`, `H_CORR` |
| Carbon | `NEE_VUT_REF`, `NEE_VUT_REF_JOINTUNC`, `GPP_NT_VUT_REF`, `GPP_DT_VUT_REF`, `RECO_NT_VUT_REF`, `RECO_DT_VUT_REF` |
| Quality | `_QC` of `TA_F`, `VPD_F`, `P_F`, `SW_IN_F`, `LW_IN_F`, `PA_F`, `WS_F`, `PPFD_IN`, `NETRAD`, `CO2_F_MDS`, `G_F_MDS`, `LE_F_MDS`, `H_F_MDS`, `NEE_VUT_REF`, `SWC_F_MDS`, `TS_F_MDS` |

- Names, values and units are FLUXNET's; each variable's definition from the archive is its `description`.
- Unit strings that are not valid CF are renamed to the same unit in CF, with the original in `provider_units`: `deg C` is `degC`, `gC m-2 d-1` is `g m-2 d-1`, `µmolCO2 m-2 s-1` is `umol m-2 s-1`. The species (carbon, CO2, photons) is in the description, not the unit.
- `-9999` becomes NaN. A variable a site does not measure, and a depth it has no sensor at, are NaN, so every site has the same variables.
- Global attributes record provenance: `institution`, `source`, `license`, `history`, and every site's citation in `references`.

### What standardise changes

`fetch` changes nothing: it picks each site's current archive, checks it against the portal's SHA-256, and saves it as served.
`standardise` runs the graph below, from the archive paths to the dataset.
Each node does one thing, and its colour says what kind of thing; [ADR 2](https://github.com/NERC-CEH/xharvest/blob/main/docs/adr/0002-standardise-as-hamilton-graph.md#decision) defines each kind.
Hover over a node for a summary, or click its name for its entry under [Standardisation nodes](#standardisation-nodes), which says what it does and why.

--8<-- "docs/providers/_graphs/icos.html"

Nothing converts units, filters on quality flags, or fills gaps.
Gap-filled values come from ONEFlux, upstream; the `_QC` fractions say how much of each day was filled.

!!! note "Judgement calls"

    The nodes tagged `interprets` make choices that are xharvest's, not the provider's, and could reasonably go the other way:
    [`variables`](#xharvest._fluxnet.variables), [`descriptions`](#xharvest.icos._pipeline.descriptions), [`flag_attributes`](#xharvest.icos._pipeline.flag_attributes) and [`cell_methods`](#xharvest.icos._pipeline.cell_methods).
    Each one's entry says what it decides and why.

## About the data

What follows was checked on 2026-11-19 against UK-Cvn (UTC+0, longitude 0.16° E) and ES-Dnn (UTC+1, longitude 6.51° W), by comparing each archive's daily file with its half-hourly one.
`tests/test_icos_live.py` repeats the timestamp check, and the aggregation check for `TA_F`, `SW_IN_F` and `P_F`, on UK-Cvn.

The archives contradict themselves in places.
Each callout below names a contradiction, says what the data show, and says what `standardise` does about it.

### Timestamps

Each archive's data keep **local standard time**, UTC plus the `UTC_OFFSET` in its site metadata, with no daylight saving.

!!! warning "The archive README says local solar time; the data say local standard time"

    `SW_IN_POT`, which ONEFlux computes, peaks at 12:00-12:30 at UK-Cvn, where solar noon is 11:59 UTC, and at 13:00-13:30 at ES-Dnn, where solar noon is 12:26 UTC, 13:26 at UTC+1.
    In local solar time both would peak at about 12:00.
    `standardise` converts with `UTC_OFFSET` and ignores the README.

A **daily** value covers the local day, 00:00 to 24:00 on the file's clock.
Shifting the day by an hour either way breaks the match described under [Daily aggregation](#daily-aggregation).
`time` is the start of that day in UTC, so at UTC+0 a daily value covers the GMT day, as a COSMOS-UK daily value does, and at UTC+1 it starts at 23:00 UTC the day before.

### Daily aggregation

Every variable `standardise` keeps, apart from the uncertainties, `LE_CORR` and `H_CORR`, is the mean of the day's half-hours, to within 0.001 (0.006 mm d-1 for `P_F`), at UK-Cvn and at ES-Dnn for the variables ES-Dnn measures.
The `_REF` carbon fluxes match on most days but not all; see the second callout below.
Carbon fluxes and precipitation are means as rates, so a daily value in `g m-2 d-1` or `mm d-1` equals the sum of the half-hourly amounts.
These variables carry `cell_methods = "time: mean"`.

!!! warning "Daily `LE_CORR` and `H_CORR` are not the average of half-hourly values, as their definitions say"

    The archive defines both as "corrected [...] by energy balance closure correction factor, average from half-hourly data".
    At UK-Cvn, daily `LE_CORR` differs from the mean of half-hourly `LE_CORR` by a median of 9.4 W m-2 and up to 51 W m-2, and `H_CORR` by up to 29 W m-2.
    Nor is each one the daily `LE_F_MDS` or `H_F_MDS` times one daily factor: the two ratios differ by up to 0.42 on the same day.
    ONEFlux appears to correct the daily values at the daily scale, but the archive does not say how.
    `standardise` keeps both, with the archive's definitions, but gives them no `cell_methods`.

!!! warning "Daily `_REF` variables are not the aggregate of the half-hourly ones"

    ONEFlux chooses the reference realisation of `NEE_VUT_REF`, `GPP_*_VUT_REF` and `RECO_*_VUT_REF` separately at each resolution.
    So on some days the daily value comes from a different realisation from the half-hourly one.
    At UK-Cvn, daily `NEE_VUT_REF` differs from the daily sum of half-hourly `NEE_VUT_REF` by up to 0.46 gC m-2 d-1 (median 0.017), and `GPP_DT_VUT_REF` by up to 1.25.
    Do not aggregate half-hourly `_REF` values and expect the daily file, or compare the two.

### Units

!!! warning "Daily precipitation is a rate (`mm d-1`), not COSMOS-UK's daily total (`mm`)"

    `P_F` is the day's mean rate, which equals the day's total in millimetres; COSMOS-UK's daily `precip` is a total, in `mm`.
    No unit conversion turns one into the other.
    `standardise` leaves both as their providers give them, so a pipeline that uses both must reconcile them explicitly, knowing each value covers one day.

Unit strings that are not valid CF are renamed to the same unit in CF (see [Standardise](#standardise)); the species is in each variable's `description`, not its unit.

### Quality flags

A daily `_QC` is the fraction, from 0 to 1, of the day's half-hours that were measured or gap-filled with good quality.
Gap-filled values are part of the `_F_MDS` variables (filled by ONEFlux from similar conditions nearby in time) and the `_F` meteorology (filled from ERA5 where that fails); `_QC` is how to tell how much of a day was filled.

!!! warning "Some `_QC` columns are described as their parent variable"

    The archive's variable list gives `SWC_F_MDS_<n>_QC` the unit `%` and the definition "Soil water content, ...", and `TS_F_MDS_<n>_QC` the unit `deg C` and the soil temperature definition; the percentile `_QC` columns are mislabelled the same way.
    Their values are 0-1 fractions like every other daily `_QC`.
    `standardise` gives every `_QC` the unit `1`, raises if any value lies outside 0-1, and writes its description itself rather than taking the archive's.

### Soil profiles

FLUXNET numbers soil sensors `SWC_F_MDS_1`, `SWC_F_MDS_2`, ..., but the numbers are not depths: they skip values, and the same number means different depths at different sites and in different variables (at UK-Cvn, `SWC_F_MDS_1` and `TS_F_MDS_2` are both at 5 cm).
`standardise` stacks them on `depth`, from each sensor's height in the archive's variable list, and raises if two sensors of one variable share a depth or a sensor's depth changes within the record.
At the UK sites the sensors are between 2 and 50 cm deep.

### Archive format

!!! note "Archives differ in encoding and in unit spelling"

    Some networks write their variable list in Latin-1 (UK-Cvn, with `µ` as byte `0xB5`), others in UTF-8, and dimensionless units are spelled `adimensional` or `nondimensional`.
    The reader handles both; neither changes the standardised output.

### Other resolutions

The archives also hold half-hourly, weekly, monthly and yearly files, which this connector does not read yet.
Beyond the time axis, they differ in units (half-hourly `P_F` is `mm` per half-hour; carbon fluxes are `µmolCO2 m-2 s-1`), in what `_QC` means (half-hourly flags are categories 0-3), and in which variables they hold.

## Citing the data

The licence requires a citation for every site used.
`fetch` records each archive's citation, as the portal gives it, in its sidecar, and `standardise` lists them in the `references` attribute, for example:

> D'Acunha, B., Evans, C., Morrison, R., Riutta, T., Shuckburgh, E., van den Berg, M. (2026). Fluxnet Archive Product from Coveney, 2023–2024, FLUXNET, <https://hdl.handle.net/11676/37X3GrWRM7AEcdIt8WRasg1l>

Each archive's `DATA_POLICY_LICENSE_AND_INSTRUCTIONS.txt` gives the acknowledgements each network also requires.

## CLI

::: mkdocs-typer2
    :module: xharvest.cli.app
    :name: xharvest
    :command: icos
    :termynal: true
    :width: 80
    :prompt: ❯

Run `xharvest icos <command> --help` for a command's options; they mirror the Python API below.

## Python API

::: xharvest.icos.sites
    options:
      heading_level: 3

::: xharvest.icos.Site
    options:
      heading_level: 3

::: xharvest.icos.fetch
    options:
      heading_level: 3

::: xharvest.icos.standardise
    options:
      heading_level: 3

::: xharvest.icos.to_netcdf
    options:
      heading_level: 3

## Standardisation nodes

The nodes of the graph above, in the order their modules define them.
The FLUXNET reader is shared with other FLUXNET hubs; the rest are specific to this connector.

::: xharvest._fluxnet
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^FILL_VALUE$"]

::: xharvest.icos._pipeline
    options:
      heading_level: 3
      show_root_heading: true
      members_order: source
      filters: ["!^_", "!^QC_DESCRIPTION$", "!^TITLE$"]

## Contract types

`xharvest.icos` exports a contract type for each unit in a standardised file, and `VARIABLES`, which maps each variable's name to its type.
Annotate a node's input with one and catena checks the file against it before compute.
Import the module rather than the names, as `from xharvest import icos`, and write `icos.CarbonFlux`.
Each declares the CF unit and the coordinates `time`, `site`, `lat` and `lon`, plus `depth` for the soil profiles.
Types with the same unit and coordinates are the same object, so a type does not tell variables apart.
None declares a `Freq`; add one where it matters, as `Annotated[icos.CarbonFlux, Freq("D")]`.
Their units need `xarray_annotated.units.use_cf_units()`.

| Type | Unit | Variables |
|---|---|---|
| `AirTemperature` | `degC` | `TA_F` |
| `VapourPressureDeficit` | `hPa` | `VPD_F` |
| `Precip` | `mm d-1` | `P_F` |
| `EnergyFlux` | `W m-2` | `SW_IN_F`, `LW_IN_F`, `NETRAD`, `G_F_MDS`, `LE_F_MDS`, `LE_CORR`, `LE_CORR_JOINTUNC`, `H_F_MDS`, `H_CORR` |
| `AirPressure` | `kPa` | `PA_F` |
| `WindSpeed` | `m s-1` | `WS_F` |
| `PhotonFlux` | `umol m-2 s-1` | `PPFD_IN` |
| `CO2MoleFraction` | `umol mol-1` | `CO2_F_MDS` |
| `CarbonFlux` | `g m-2 d-1` | `NEE_VUT_REF`, `NEE_VUT_REF_JOINTUNC`, `GPP_NT_VUT_REF`, `GPP_DT_VUT_REF`, `RECO_NT_VUT_REF`, `RECO_DT_VUT_REF` |
| `QualityFraction` | `1` | The `_QC` of each variable on `(time, site)` |
| `SoilWaterContent` | `%` | `SWC_F_MDS` |
| `SoilTemperature` | `degC` | `TS_F_MDS` |
| `ProfileQualityFraction` | `1` | `SWC_F_MDS_QC`, `TS_F_MDS_QC` |

There are no catena nodes yet.
