# About the FLUXNET data

What follows was checked on 2026-11-19 against UK-Cvn (UTC+0, longitude 0.16° E) and ES-Dnn (UTC+1, longitude 6.51° W), by comparing each archive's daily file with its half-hourly one.
`tests/test_fluxnet_live.py` repeats the timestamp check, and the aggregation check for `TA_F`, `SW_IN_F` and `P_F`, on UK-Cvn.

The archives contradict themselves in places.
Each callout below names a contradiction, says what the data show, and says what `standardise` does about it.

In short:

- `time` is the start, in UTC, of the site's local standard day, so at a UTC+1 site a daily value starts at 23:00 UTC the day before ([Timestamps](#timestamps)).
- Every variable kept is the mean of the day's half-hours, except `LE_CORR`, `H_CORR` and the uncertainties, which have no `cell_methods` ([Daily aggregation](#daily-aggregation)).
- Daily `_REF` carbon fluxes may come from a different realisation from the half-hourly ones, so do not compare them with aggregated half-hourly values.
- `P_F` is the day's mean rate in `mm d-1`, which equals the day's total in millimetres ([Units](#units)).
- Each `_QC` is the fraction, 0 to 1, of the day's half-hours that were measured or gap-filled with good quality, whatever the archive's variable list says ([Quality flags](#quality-flags)).
- Soil sensors are stacked on `depth` from their heights; FLUXNET's sensor numbers are not depths ([Soil profiles](#soil-profiles)).

## Timestamps

Each archive's data keep **local standard time**, UTC plus the `UTC_OFFSET` in its site metadata, with no daylight saving.

!!! warning "The archive README says local solar time; the data say local standard time"

    `SW_IN_POT`, which ONEFlux computes, peaks at 12:00-12:30 at UK-Cvn, where solar noon is 11:59 UTC, and at 13:00-13:30 at ES-Dnn, where solar noon is 12:26 UTC, 13:26 at UTC+1.
    In local solar time both would peak at about 12:00.
    `standardise` converts with `UTC_OFFSET` and ignores the README.

A **daily** value covers the local day, 00:00 to 24:00 on the file's clock.
Shifting the day by an hour either way breaks the match described under [Daily aggregation](#daily-aggregation).
`time` is the start of that day in UTC, so at UTC+0 a daily value covers the GMT day, as a COSMOS-UK daily value does, and at UTC+1 it starts at 23:00 UTC the day before.

## Daily aggregation

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

## Units

!!! warning "Daily precipitation is a rate (`mm d-1`), not COSMOS-UK's daily total (`mm`)"

    `P_F` is the day's mean rate, which equals the day's total in millimetres; COSMOS-UK's daily `precip` is a total, in `mm`.
    No unit conversion turns one into the other.
    `standardise` leaves both as their providers give them, so a pipeline that uses both must reconcile them explicitly, knowing each value covers one day.

Unit strings that are not valid CF are renamed to the same unit in CF (see [Standardise](index.md#standardise)); the species is in each variable's `description`, not its unit.

## Quality flags

A daily `_QC` is the fraction, from 0 to 1, of the day's half-hours that were measured or gap-filled with good quality.
Gap-filled values are part of the `_F_MDS` variables (filled by ONEFlux from similar conditions nearby in time) and the `_F` meteorology (filled from ERA5 where that fails); `_QC` is how to tell how much of a day was filled.

!!! warning "Some `_QC` columns are described as their parent variable"

    The archive's variable list gives `SWC_F_MDS_<n>_QC` the unit `%` and the definition "Soil water content, ...", and `TS_F_MDS_<n>_QC` the unit `deg C` and the soil temperature definition; the percentile `_QC` columns are mislabelled the same way.
    Their values are 0-1 fractions like every other daily `_QC`.
    `standardise` gives every `_QC` the unit `1`, raises if any value lies outside 0-1, and writes its description itself rather than taking the archive's.

## Soil profiles

FLUXNET numbers soil sensors `SWC_F_MDS_1`, `SWC_F_MDS_2`, ..., but the numbers are not depths: they skip values, and the same number means different depths at different sites and in different variables (at UK-Cvn, `SWC_F_MDS_1` and `TS_F_MDS_2` are both at 5 cm).
`standardise` stacks them on `depth`, from each sensor's height in the archive's variable list, and raises if two sensors of one variable share a depth or a sensor's depth changes within the record.
At the UK sites the sensors are between 2 and 50 cm deep.

## Archive format

!!! note "Archives differ in encoding and in unit spelling"

    Some networks write their variable list in Latin-1 (UK-Cvn, with `µ` as byte `0xB5`), others in UTF-8, and dimensionless units are spelled `adimensional` or `nondimensional`.
    The reader handles both; neither changes the standardised output.

## Other resolutions

The archives also hold half-hourly, weekly, monthly and yearly files, which this connector does not read yet.
Beyond the time axis, they differ in units (half-hourly `P_F` is `mm` per half-hour; carbon fluxes are `µmolCO2 m-2 s-1`), in what `_QC` means (half-hourly flags are categories 0-3), and in which variables they hold.
