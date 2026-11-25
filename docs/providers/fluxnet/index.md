# FLUXNET

The [ICOS Carbon Portal](https://www.icos-cp.eu) hosts the FLUXNET data product, eddy-covariance fluxes and meteorology processed with [ONEFlux](https://github.com/fluxnet/ONEFlux) v1.3, for several hundred sites.
`xharvest.fluxnet` downloads it and standardises the daily files for catena and xarray.

| | |
|---|---|
| Install | `pip install "xharvest[fluxnet] @ git+https://github.com/NERC-CEH/xharvest"` |
| Credentials | None |
| Licence | CC BY 4.0, as each archive's data policy states |
| Cite | One citation per site (see [Citing the data](#citing-the-data)) |
| Resolution | Daily only |
| catena nodes | None yet (see [Using with catena](catena.md)) |

The connector is partial ([#11](https://github.com/NERC-CEH/xharvest/issues/11)): daily files only, a fixed set of variables for soil moisture and ecosystem carbon modelling, tested on UK sites.
The archives come from several networks, not only ICOS: the first part of the file name says which (`ICOS`, `EUF` for the European Fluxes Database, `JPF`, `CNF`, `KOF`, `FLX`, `SAEON`).
In the UK only UK-AMo is an ICOS station; the other UK sites are `EUF`.

## Download

```python
from xharvest import fluxnet

fluxnet.sites()  # site codes, names, locations, records and file names
raw = fluxnet.fetch(["UK-Cvn", "UK-AMo"], "data/raw")
```

or from the command line:

```sh
xharvest fluxnet sites
xharvest fluxnet fetch UK-Cvn UK-AMo --out data/raw
```

- `fetch` downloads each site's whole archive (20-250 MB), with a `.meta.json` provenance sidecar recording the archive's citation and persistent identifier.
- There is no date range: the portal serves whole-site archives only. Select a period after standardising.
- Each download is checked against the SHA-256 the portal publishes.
- Files keep the portal's name, e.g. `EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip`, so a new release arrives as a new file.
- An archive that already holds the same object is skipped; pass `overwrite=True` (`--overwrite`) to download again.

`sites()` gives each archive's site code, name, location and record, so plain Python picks sites out.
For example, the UK sites with at least five years of data:

```python
chosen = [
    s.id
    for s in fluxnet.sites()
    if s.id.startswith("UK-") and s.end.year - s.start.year >= 5
]
```

## Standardise

```python
fluxnet.to_netcdf(raw, "data/fluxnet.nc")
```

```sh
xharvest fluxnet standardise data/raw/*.zip --out data/fluxnet.nc
```

Sidecars among the paths are skipped, so a glob over the download directory works.
Sites whose data keep different local standard times (see [Timestamps](data.md#timestamps)) cannot share a file, and raise; the UK sites are all UTC+0.

The result has dims `(time, site, depth)`:

| Name | Kind | Notes |
|---|---|---|
| `time` | dim | UTC start of the site's local standard day, as naive `datetime64` |
| `site` | dim | FLUXNET site code, e.g. `UK-Cvn` |
| `depth` | dim | Soil sensor depth, metres below ground, positive down |
| `site_name`, `lat`, `lon`, `altitude` | coord on `site` | From the archive's site metadata |
| `utc_offset`, `igbp`, `network` | coord on `site` | Hours from UTC to the data's clock; IGBP land cover; network code |
| `time_bounds` | coord on `(time, nv)` | The day each value covers |
| [the variables below](#variables) | data, on `(time, site)`, or `(time, site, depth)` for the soil profiles | |

- Names, values and units are FLUXNET's; each variable's definition from the archive is its `description`.
- Unit strings that are not valid CF are renamed to the same unit in CF, with the original in `provider_units`: `deg C` is `degC`, `gC m-2 d-1` is `g m-2 d-1`, `µmolCO2 m-2 s-1` is `umol m-2 s-1`. The species (carbon, CO2, photons) is in the description, not the unit.
- `-9999` becomes NaN. A variable a site does not measure, and a depth it has no sensor at, are NaN, so every site has the same variables.
- Global attributes record provenance: `institution`, `source`, `license`, `history`, and every site's citation in `references`.
- Nothing converts units, filters on quality flags, or fills gaps; [How standardisation works](standardise.md) shows every step.

Open the file with `xr.open_dataset("data/fluxnet.nc")`.
The test fixtures, two UK sites over overlapping fortnights, print as:

--8<-- "docs/providers/_variables/fluxnet-dataset.md"

### Variables

`standardise` keeps these variables, and the `_QC` of those marked, whatever else an archive holds.
Each `_QC` is the fraction of the day's half-hours that were measured or gap-filled with good quality (see [Quality flags](data.md#quality-flags)).
Units are the CF units `standardise` writes; descriptions are the archives' own, drawn from the test fixtures (UK-Ags and UK-Cvn).

--8<-- "docs/providers/_variables/fluxnet.md"

## Citing the data

The licence requires a citation for every site used.
`fetch` records each archive's citation, as the portal gives it, in its sidecar, and `standardise` lists them in the `references` attribute, for example:

> D'Acunha, B., Evans, C., Morrison, R., Riutta, T., Shuckburgh, E., van den Berg, M. (2026). Fluxnet Archive Product from Coveney, 2023–2024, FLUXNET, <https://hdl.handle.net/11676/37X3GrWRM7AEcdIt8WRasg1l>

Each archive's `DATA_POLICY_LICENSE_AND_INSTRUCTIONS.txt` gives the acknowledgements each network also requires.

## More

- [About the data](data.md): timestamps, daily aggregation, units, quality flags and soil profiles, where the archives contradict themselves, as checked against the data.
- [How standardisation works](standardise.md): every step from the downloaded files to the netCDF, and the judgement calls xharvest makes.
- [Using with catena](catena.md): contract types; there are no nodes yet.
- [Reference](reference.md): the CLI and the Python API.
