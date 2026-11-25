import csv
import io
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from xharvest.errors import ProviderError
from xharvest.icos import GROUPS, VARIABLES, standardise, to_netcdf
from xharvest.icos import _pipeline as pl
from xharvest.provenance import sidecar_path


def _by_site(paths):
    return {p.name.split("_")[1]: p for p in paths}


def _raw_entries(path):
    """The archive's ancillary entries, read independently of the pipeline."""
    with zipfile.ZipFile(path) as archive:
        (name,) = [n for n in archive.namelist() if "_ANCILLARY_" in n]
        text = archive.read(name).decode("utf-8")
    entries = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(text)):
        entries[row["VARIABLE_GROUP"], row["GROUP_ID"]][row["VARIABLE"]] = row[
            "DATAVALUE"
        ]
    return entries


def _without_ancillary_rows(text, keep):
    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(
        [rows[0], *(r for r in rows[1:] if keep(r))]
    )
    return out.getvalue()


@pytest.mark.parametrize("group", GROUPS)
def test_each_group_is_records_holding_its_values(icos_raw, group):
    ds = standardise(icos_raw, group)
    assert set(ds.dims) == {"record", "nv"}
    assert set(ds.data_vars) == set(VARIABLES[group]) == set(GROUPS[group])
    for name in ["site", "site_name", "lat", "lon", "time", "time_bounds"]:
        assert name in ds.coords


def test_every_entry_with_a_value_is_one_record(icos_raw):
    for path in icos_raw:
        site = path.name.split("_")[1]
        raw = _raw_entries(path)
        for group, names in GROUPS.items():
            expected = [
                e
                for (g, _), e in raw.items()
                if g == f"GRP_{group}"
                and any(e.get(n, "") for n in names)
                and (group != "BIOMASS" or e.get("BIOMASS_UNIT") == "kgDM m-2")
            ]
            ds = standardise(icos_raw, group)
            assert int((ds.site == site).sum()) == len(expected), (site, group)


def test_values_are_the_archives_own(icos_raw):
    har = _by_site(icos_raw)["DE-Har"]
    clay = sorted(
        float(e["SOIL_TEX_CLAY"])
        for (g, _), e in _raw_entries(har).items()
        if g == "GRP_SOIL_TEX" and e.get("SOIL_TEX_CLAY")
    )
    ds = standardise(icos_raw, "SOIL_TEX")
    found = ds.SOIL_TEX_CLAY.where(ds.site == "DE-Har", drop=True).values
    assert sorted(found[~np.isnan(found)]) == clay


def test_qualifiers_are_coordinates_padded_across_stations(icos_raw):
    ds = standardise(icos_raw, "LAI")
    assert set(np.unique(ds.LAI_TYPE)) >= {"GAI"}
    assert ds.LAI_STATISTIC_NUMBER.dtype.kind == "f"
    assert ds.LAI_TYPE.dtype.kind == "U"
    # A qualifier only one station gives is empty at the other's records.
    vegtype = ds.LAI_VEGTYPE.where(ds.site == "UK-AMo", drop=True)
    assert set(np.unique(vegtype)) == {""}


def test_soil_depths_are_numbers_in_cm(icos_raw):
    ds = standardise(icos_raw, "SOIL_TEX")
    assert ds.SOIL_TEX_PROFILE_MIN.dtype.kind == "f"
    assert ds.SOIL_TEX_PROFILE_MIN.attrs["units"] == "cm"


def test_variable_attributes(icos_raw):
    ds = standardise(icos_raw, "SOIL_TEX")
    assert ds.SOIL_TEX_CLAY.attrs == {
        "units": "%",
        "provider_units": "%",
        "description": "Clay content",
    }
    assert ds.SOIL_TEX_FIELD_CAP.attrs["provider_units"] == "%vol"
    assert ds.SOIL_TEX_FIELD_CAP.attrs["units"] == "%"
    biomass = standardise(icos_raw, "BIOMASS").BIOMASS
    assert biomass.attrs["units"] == "kg m-2"
    assert biomass.attrs["provider_units"] == "kgDM m-2"
    stock = standardise(icos_raw, "SOIL_STOCK").SOIL_STOCK_C_ORG
    assert stock.attrs["units"] == "g m-2"
    assert stock.attrs["provider_units"] == "g C m-2"


def test_global_attributes(icos_raw):
    ds = standardise(icos_raw, "LAI")
    assert ds.attrs["title"] == "ICOS ecosystem station ancillary data: LAI"
    assert "creativecommons.org/licenses/by/4.0" in ds.attrs["license"]
    assert ds.attrs["references"].count("ETC L2 ARCHIVE") == 2
    assert ds.attrs["history"].count("retrieved https://data.icos-cp.eu/") == 2
    assert ds.time.attrs["bounds"] == "time_bounds"


@pytest.mark.parametrize(
    ("value", "start", "end"),
    [
        ("2023", "2023-01-01", "2024-01-01"),
        ("202306", "2023-06-01", "2023-07-01"),
        ("20230615", "2023-06-15", "2023-06-16"),
        ("2023061512", "2023-06-15T12", "2023-06-15T13"),
        ("202306151230", "2023-06-15T12:30", "2023-06-15T12:30"),
        ("20230615123015", "2023-06-15T12:30:15", "2023-06-15T12:30:15"),
    ],
)
def test_a_date_names_the_period_its_precision_gives(value, start, end):
    assert pl._period(value) == (
        np.datetime64(start, "ns"),
        np.datetime64(end, "ns"),
    )


@pytest.mark.parametrize("value", ["", "-", "20231"])
def test_an_unreadable_date_is_nat(value):
    assert all(np.isnat(t) for t in pl._period(value))


def test_a_start_and_end_give_the_period(icos_raw):
    entry = {"LAI": "1", "LAI_DATE_START": "202306", "LAI_DATE_END": "20230710"}
    path = Path("x.zip")
    ((time, start, end),) = pl.periods({path: {"LAI": [entry]}})[path].values()
    assert time[0] == np.datetime64("2023-06-01", "ns")
    assert start[0] == np.datetime64("2023-06-01", "ns")
    assert end[0] == np.datetime64("2023-07-11", "ns")


def _set_first_lai(rewrite_archive, path, dest, value):
    dest.parent.mkdir(exist_ok=True)
    done = []

    def change(text):
        rows = list(csv.reader(io.StringIO(text)))
        for row in rows[1:]:
            if row[3] == "LAI" and not done:
                row[4] = value
                done.append(row)
        out = io.StringIO()
        csv.writer(out, lineterminator="\n").writerows(rows)
        return out.getvalue()

    rewrite_archive(path, dest, "_ANCILLARY_", change)
    sidecar_path(dest).write_bytes(sidecar_path(path).read_bytes())
    return dest


def test_a_decimal_comma_is_read_as_a_point(icos_raw, rewrite_archive, tmp_path):
    amo = _by_site(icos_raw)["UK-AMo"]
    changed = _set_first_lai(rewrite_archive, amo, tmp_path / "x" / amo.name, "0,5")
    ds = standardise([changed], "LAI")
    assert 0.5 in ds.LAI.values


def test_a_value_that_is_not_a_number_raises(icos_raw, rewrite_archive, tmp_path):
    amo = _by_site(icos_raw)["UK-AMo"]
    changed = _set_first_lai(rewrite_archive, amo, tmp_path / "x" / amo.name, "n/a")
    with pytest.raises(ProviderError, match="'n/a'"):
        standardise([changed], "LAI")


def test_carbon_biomass_is_dropped_and_unknown_units_raise(
    icos_raw, rewrite_archive, tmp_path
):
    amo = _by_site(icos_raw)["UK-AMo"]
    before = standardise([amo], "BIOMASS").sizes["record"]
    for unit, outcome in [("gC m-2", "dropped"), ("t ha-1", "raises")]:
        dest = tmp_path / unit.replace(" ", "") / amo.name
        dest.parent.mkdir()

        def change(text, unit=unit):
            return text.replace("kgDM m-2", unit, 1)

        rewrite_archive(amo, dest, "_ANCILLARY_", change)
        sidecar_path(dest).write_bytes(sidecar_path(amo).read_bytes())
        if outcome == "dropped":
            assert standardise([dest], "BIOMASS").sizes["record"] == before - 1
        else:
            with pytest.raises(ProviderError, match="t ha-1"):
                standardise([dest], "BIOMASS")


def test_an_archive_without_ancillary_data_raises(icos_raw, rewrite_archive, tmp_path):
    amo = _by_site(icos_raw)["UK-AMo"]
    (tmp_path / "x").mkdir()
    dest = rewrite_archive(
        amo, tmp_path / "x" / amo.name, "_ANCILLARY_", lambda _: None
    )
    sidecar_path(dest).write_bytes(sidecar_path(amo).read_bytes())
    with pytest.raises(ProviderError, match="_ANCILLARY_"):
        standardise([dest], "LAI")


def test_a_group_a_station_lacks_is_empty(icos_raw):
    amo = _by_site(icos_raw)["UK-AMo"]
    ds = standardise([amo], "SOIL_TEX")
    assert ds.sizes["record"] == 0
    assert set(ds.data_vars) == set(GROUPS["SOIL_TEX"])


def test_an_unknown_group_raises(icos_raw):
    with pytest.raises(ValueError, match="unknown group 'GRP_LAI'"):
        standardise(icos_raw, "GRP_LAI")


def test_sidecars_among_the_paths_are_skipped(icos_raw):
    paths = [*icos_raw, *(sidecar_path(p) for p in icos_raw)]
    assert standardise(paths, "LAI").sizes == standardise(icos_raw, "LAI").sizes
    with pytest.raises(ValueError, match="no ETC L2"):
        standardise([sidecar_path(icos_raw[0])], "LAI")


def test_missing_sidecar_raises(icos_raw):
    sidecar_path(icos_raw[0]).unlink()
    with pytest.raises(FileNotFoundError):
        standardise(icos_raw, "LAI")


@pytest.mark.parametrize("group", GROUPS)
def test_to_netcdf_round_trips(icos_raw, tmp_path, group):
    out = to_netcdf(icos_raw, tmp_path / "out" / f"{group}.nc", group)
    expected = standardise(icos_raw, group)
    with xr.open_dataset(out) as ds:
        xr.testing.assert_identical(ds.reset_coords(), expected.reset_coords())
