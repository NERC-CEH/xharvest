"""Tests of the shared FLUXNET reader's nodes, each called on its own."""

import re
import zipfile
from pathlib import Path

import numpy as np
import pytest

from xharvest.errors import ProviderError
from xharvest.icos import _fluxnet as fx

FIXTURES = Path(__file__).parent / "fixtures" / "icos"
CVN = FIXTURES / "EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip"
AGS = FIXTURES / "EUF_UK-Ags_FLUXNET_2023-2025_v1.3_r1.zip"
PROFILED = ("SWC_F_MDS", "TS_F_MDS")


def _texts(*paths):
    return fx.archive_texts(list(paths))


def _variables(*paths):
    return fx.variables(fx.variable_entries(_texts(*paths)))


def _tables(*paths):
    texts = _texts(*paths)
    return fx.described_tables(
        fx.tables(fx.raw_tables(texts)), fx.variables(fx.variable_entries(texts))
    )


def _profiles(path):
    return fx.soil_profiles(_tables(path), _variables(path), PROFILED)[path]


def test_sites_reads_site_metadata():
    site = fx.sites(_texts(CVN))[CVN]
    assert (site.site, site.site_name) == ("UK-Cvn", "Coveney")
    assert (site.lat, site.lon) == pytest.approx((52.43339, 0.162177))
    assert site.elevation == pytest.approx(-0.67)
    assert site.utc_offset == 0
    assert (site.igbp, site.network) == ("GRA", "EUF")
    assert site.processing_center == "EUDB_ICOS"
    assert site.oneflux_version.startswith("1.3")


def test_licences_reads_the_data_policy():
    assert fx.licences(_texts(CVN)) == {CVN: "CC-BY-4.0"}


def test_raw_tables_keep_fills_and_tables_decode_them():
    raw = fx.raw_tables(_texts(CVN))[CVN]
    assert raw.dates[0] == np.datetime64("2023-09-01")
    assert raw.dates[-1] == np.datetime64("2023-09-14")
    # The raw file has -9999 in this column for some days.
    assert np.any(raw.columns["SWC_F_MDS_2"] == -9999)
    decoded = fx.tables({CVN: raw})[CVN]
    assert not any(np.any(v == -9999) for v in decoded.columns.values())
    assert np.isnan(decoded.columns["SWC_F_MDS_2"]).any()
    np.testing.assert_array_equal(decoded.columns["TA_F"], raw.columns["TA_F"])


def test_every_column_has_a_variable():
    table = _tables(CVN)[CVN]
    assert set(table.columns) <= set(_variables(CVN)[CVN])
    assert _variables(CVN)[CVN]["TA_F"].units == "deg C"


def test_reads_latin1_unit_strings():
    # This archive's BIFVARINFO is Latin-1, with µ as 0xB5.
    assert _variables(CVN)[CVN]["PPFD_IN"].units == "µmolPhoton m-2 s-1"


def test_reads_utf8_unit_strings(tmp_path):
    path = tmp_path / "a.zip"
    with zipfile.ZipFile(CVN) as src, zipfile.ZipFile(path, "w") as out:
        for info in src.infolist():
            raw = src.read(info)
            if "BIFVARINFO" in info.filename:
                raw = raw.decode("latin-1").encode("utf-8")
            out.writestr(info, raw)
    assert _variables(path)[path]["PPFD_IN"].units == "µmolPhoton m-2 s-1"


def test_variables_keep_the_first_entry():
    first = fx.Variable("SW_IN_F", "W m-2", "first", 2.0)
    later = fx.Variable("SW_IN_F", "W m-2", "later", 3.0)
    kept = fx.variables({CVN: {"SW_IN_F": [first, later]}})
    assert kept[CVN]["SW_IN_F"] is first


@pytest.mark.parametrize(
    "later",
    [
        fx.Variable("SWC_F_MDS_1", "kPa", "", -0.05),
        fx.Variable("SWC_F_MDS_1", "%", "", -0.1),
    ],
    ids=["unit", "depth"],
)
def test_variables_reject_a_change_of_unit_or_soil_depth(later):
    first = fx.Variable("SWC_F_MDS_1", "%", "", -0.05)
    with pytest.raises(ProviderError, match="changes unit or depth"):
        fx.variables({CVN: {"SWC_F_MDS_1": [first, later]}})


def test_soil_profiles_map_depths_not_indices():
    profiles = _profiles(CVN)
    assert profiles["SWC_F_MDS"] == {
        0.05: "SWC_F_MDS_1",
        0.1: "SWC_F_MDS_2",
        0.15: "SWC_F_MDS_3",
        0.25: "SWC_F_MDS_5",
    }
    # The same depths carry other indices in another variable.
    assert profiles["TS_F_MDS"][0.05] == "TS_F_MDS_2"
    assert list(_profiles(AGS)["SWC_F_MDS"]) == [0.05, 0.1, 0.2, 0.3, 0.4, 0.5]


def test_soil_profiles_reject_two_sensors_at_one_depth(rewrite_archive, tmp_path):
    def same_height(text):
        return text.replace("VAR_INFO_HEIGHT,-0.1\n", "VAR_INFO_HEIGHT,-0.05\n")

    path = rewrite_archive(CVN, tmp_path / "a.zip", "BIFVARINFO", same_height)
    with pytest.raises(ProviderError, match=r"both at 0\.05 m"):
        _profiles(path)


def test_times_are_the_utc_start_of_the_local_day(rewrite_archive, tmp_path):
    def plus_one(text):
        return re.sub(r"(GRP_UTC_OFFSET,UTC_OFFSET,)0", r"\g<1>1", text)

    path = rewrite_archive(CVN, tmp_path / "a.zip", "_FLUXNET_BIF_", plus_one)
    times = fx.times(_tables(path), fx.sites(_texts(path)))[path]
    assert times[0] == np.datetime64("2023-08-31T23:00")


def test_cf_units_rename_and_reject_unknown_strings():
    kept = {CVN: {"TA_F": fx.Variable("TA_F", "deg C", "", None)}}
    assert fx.cf_units(kept) == {CVN: {"TA_F": "degC"}}
    unknown = {CVN: {"X": fx.Variable("X", "furlongs", "", None)}}
    with pytest.raises(ProviderError, match="furlongs"):
        fx.cf_units(unknown)


def test_cf_units_are_valid():
    from xarray_annotated.units import assert_valid_unit, use_cf_units

    use_cf_units()
    for units in fx.CF_UNITS.values():
        assert_valid_unit(units, units)


def test_column_without_variable_raises(rewrite_archive, tmp_path):
    def drop_ta_f(text):
        return re.sub(r"VAR_INFO_VARNAME,TA_F\b", "VAR_INFO_VARNAME,TA_X", text)

    path = rewrite_archive(CVN, tmp_path / "a.zip", "BIFVARINFO", drop_ta_f)
    with pytest.raises(ProviderError, match="no BIFVARINFO entry for TA_F"):
        _tables(path)


def test_missing_member_raises(rewrite_archive, tmp_path):
    path = rewrite_archive(CVN, tmp_path / "a.zip", "_FLUXMET_DD_", lambda _: None)
    with pytest.raises(ProviderError, match="_FLUXMET_DD_"):
        _texts(path)


def test_not_a_zip_raises(tmp_path):
    path = tmp_path / "a.zip"
    path.write_text("not a zip")
    with pytest.raises(ProviderError, match="not a ZIP"):
        _texts(path)
