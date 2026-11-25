# About the ICOS ancillary data

What follows was checked on 2026-11-25 against the ancillary file of every current ETC L2 archive on the portal, read by HTTP range requests rather than downloading whole archives, and by running the standardisation's nodes on each of the 84 files.
`tests/test_icos_live.py` repeats the fetch and standardisation for UK-AMo.

In short:

- 84 of 93 stations have ancillary measurements, and fewer have soil measurements than vegetation ones ([Coverage](#coverage)).
- One group holds measurements of different things, told apart partly by free text, so `standardise` keeps every record and every qualifier ([Telling records apart](#telling-records-apart)).
- A date is as precise as it is long, from a year to a second ([Dates](#dates)).
- Biomass has its unit per record; a few records are in carbon rather than dry matter ([Units](#units)).

## Coverage

| | Stations |
|---|---|
| Current ETC L2 archive | 93 |
| With an ancillary file | 84 |
| `GRP_LAI` | 82 (median 18 measurement dates per station, 1-98) |
| `GRP_BIOMASS` | 80 (median 7 dates, 1-70) |
| `GRP_HEIGHTC` | 80 |
| `GRP_SOIL_TEX` | 54 |
| `GRP_SOIL_STOCK` | 31 |

The nine stations without an ancillary file are CH-BaK, DE-BeR, FI-Kvr, FI-Tvm, GR-HeK, GR-HeM, IT-OXm, IT-Sas and SE-Oes.
A group can be present with no values in it: GL-ZaH's soil stock entries give depths and dates but no stocks, so `standardise` drops them.

Other groups the archives hold, which `standardise` does not read, include soil chemistry (47 stations), species composition, tree counts, diameters and basal area, litter, soil classification, water retention curves and water table depth.

## Telling records apart

A group holds measurements of several kinds, and the archive tells them apart by qualifiers: `LAI_TYPE` (`GAI`, `PAI` or `LAI`), `LAI_CANOPY_TYPE` (`Overstory`, `Understory` or `Total`), `*_STATISTIC` (mean, standard deviation, minimum, ...), `*_SPP` for one species, `BIOMASS_ORGAN`, and soil depths.

!!! warning "The structured qualifiers do not always tell records apart"

    Among LAI records without a species, 434 of 4,299 combinations of station, date, type, canopy and statistic have more than one record.
    At SE-Sto on 2023-06-15 there are two "GAI, Overstory, Mean" records, 0.18 and 0.83.
    Only the free-text `LAI_APPROACH` tells them apart: one is "Total vascular GAI", the other "Total moss cover, estimated visually".
    `standardise` keeps both, with their approaches, rather than guess which is which.

`BIOMASS_ORGAN` is free text in practice: `total AG`, `Total AG` and `Total aboveground` all occur, 1,000-1,500 records each.
`standardise` keeps them as written.

## Dates

A BIF date has the precision of its length: `2023` (77 records), `202306` (32), `20230615` (the large majority), `2023061512` (57), `202306151200` (1,487) or `20230615120000` (6).
Some records give a period instead, with `*_DATE_START` and `*_DATE_END`.
`time_bounds` is the period a record's dates name: the year, month or day for a date, the instant for one with minutes, and from start to end for a period.
`time` is the start of `*_DATE`, or of the period where there is none.

The dates are the station's local dates; the archive does not say which time zone, and `standardise` does not convert them.
Soil samples can be decades old and dated only to the year (GL-ZaH's texture to 1997), so a soil record's date says when it was sampled.

## Units

Each value's unit comes from the archive's variable dictionary, `BIF_Ancillary_Variables.csv`, which is the same file in the three archives checked (UK-AMo's final and interim, and DE-Har's).
Biomass is the exception: its unit is per record, in `BIOMASS_UNIT`.

!!! warning "Biomass is mostly dry matter, sometimes carbon"

    Of 17,273 biomass records, 17,172 are in `kgDM m-2` and 101 in `gC m-2`.
    The two weigh different things, so they cannot share a variable, and the conversion between them depends on the tissue's carbon fraction.
    `standardise` keeps the dry matter records and drops the carbon ones.

The soil texture fractions `SOIL_TEX_SAND`, `_SILT`, `_CLAY` and `_ROCK` are in `%`, which the dictionary does not qualify; the hydraulic properties `SOIL_TEX_FIELD_CAP`, `_WILT`, `_SAT` and `_WATER_HOLD_CAP` are in `%vol`, which `standardise` writes as `%` with `provider_units = "%vol"`.
Soil stocks are in `g m-2` of carbon, nitrogen, phosphorus or potassium over the layer between `*_PROFILE_MIN` and `*_PROFILE_MAX`, in cm from the reference surface `*_PROFILE_ZERO_REF` names.
At IT-Cp2, organic horizons above the mineral soil have negative depths.

!!! warning "One value has a decimal comma"

    One biomass value of about 17,000 is written `7,9`.
    `standardise` reads a value with one comma and no point as a decimal comma, and raises on any other value that is not a number.
