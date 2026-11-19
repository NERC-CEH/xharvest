import re
import zipfile
from pathlib import Path

import numpy as np
import pytest

from xharvest._fluxnet import CF_UNITS, Variable, read_daily
from xharvest.errors import ProviderError

FIXTURES = Path(__file__).parent / "fixtures" / "icos"
CVN = FIXTURES / "EUF_UK-Cvn_FLUXNET_2023-2024_v1.3_r1.zip"
AGS = FIXTURES / "EUF_UK-Ags_FLUXNET_2023-2025_v1.3_r1.zip"


def test_reads_site_metadata():
    archive = read_daily(CVN)
    assert (archive.site, archive.site_name) == ("UK-Cvn", "Coveney")
    assert (archive.lat, archive.lon) == pytest.approx((52.43339, 0.162177))
    assert archive.elevation == pytest.approx(-0.67)
    assert archive.utc_offset == 0
    assert (archive.igbp, archive.network) == ("GRA", "EUF")
    assert archive.processing_center == "EUDB_ICOS"
    assert archive.oneflux_version.startswith("1.3")
    assert archive.licence == "CC-BY-4.0"


def test_reads_dates_and_decodes_fills():
    archive = read_daily(CVN)
    assert archive.dates[0] == np.datetime64("2023-09-01")
    assert archive.dates[-1] == np.datetime64("2023-09-14")
    assert len(archive.columns["TA_F"]) == 14
    assert not any(np.any(values == -9999) for values in archive.columns.values())
    # The raw file has -9999 in this column for some days.
    assert np.isnan(archive.columns["SWC_F_MDS_2"]).any()


def test_every_column_has_a_variable():
    archive = read_daily(CVN)
    assert set(archive.columns) <= set(archive.variables)
    assert archive.variables["TA_F"].units == "deg C"


def test_reads_latin1_unit_strings():
    # This archive's BIFVARINFO is Latin-1, with µ as 0xB5.
    archive = read_daily(CVN)
    assert archive.variables["PPFD_IN"].units == "µmolPhoton m-2 s-1"
    assert archive.variables["PPFD_IN"].cf_units == "umol m-2 s-1"


def test_reads_utf8_unit_strings(tmp_path):
    with zipfile.ZipFile(CVN) as src, zipfile.ZipFile(tmp_path / "a.zip", "w") as out:
        for info in src.infolist():
            raw = src.read(info)
            if "BIFVARINFO" in info.filename:
                raw = raw.decode("latin-1").encode("utf-8")
            out.writestr(info, raw)
    archive = read_daily(tmp_path / "a.zip")
    assert archive.variables["PPFD_IN"].units == "µmolPhoton m-2 s-1"


def test_profiles_map_depths_not_indices():
    archive = read_daily(CVN)
    assert archive.profile("SWC_F_MDS") == {
        0.05: "SWC_F_MDS_1",
        0.1: "SWC_F_MDS_2",
        0.15: "SWC_F_MDS_3",
        0.25: "SWC_F_MDS_5",
    }
    # The same depths carry other indices in another variable.
    assert archive.profile("TS_F_MDS")[0.05] == "TS_F_MDS_2"
    assert list(read_daily(AGS).profile("SWC_F_MDS")) == [
        0.05,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
    ]


def test_profile_rejects_two_sensors_at_one_depth(rewrite_archive, tmp_path):
    def same_height(text):
        return text.replace("VAR_INFO_HEIGHT,-0.1\n", "VAR_INFO_HEIGHT,-0.05\n")

    path = rewrite_archive(CVN, tmp_path / "a.zip", "BIFVARINFO", same_height)
    with pytest.raises(ProviderError, match=r"both at 0\.05 m"):
        read_daily(path).profile("SWC_F_MDS")


def test_time_is_utc_start_of_local_day(rewrite_archive, tmp_path):
    def plus_one(text):
        return re.sub(r"(GRP_UTC_OFFSET,UTC_OFFSET,)0", r"\g<1>1", text)

    path = rewrite_archive(CVN, tmp_path / "a.zip", "_FLUXNET_BIF_", plus_one)
    archive = read_daily(path)
    assert archive.utc_offset == 1
    assert archive.time[0] == np.datetime64("2023-08-31T23:00")


def test_unknown_unit_raises():
    variable = Variable("X", "furlongs", "", None)
    with pytest.raises(ProviderError, match="furlongs"):
        _ = variable.cf_units


def test_cf_units_are_valid():
    from xarray_annotated.units import assert_valid_unit, use_cf_units

    use_cf_units()
    for units in CF_UNITS.values():
        assert_valid_unit(units, units)


def test_column_without_variable_raises(rewrite_archive, tmp_path):
    def drop_ta_f(text):
        return re.sub(r"VAR_INFO_VARNAME,TA_F\b", "VAR_INFO_VARNAME,TA_X", text)

    path = rewrite_archive(CVN, tmp_path / "a.zip", "BIFVARINFO", drop_ta_f)
    with pytest.raises(ProviderError, match="no BIFVARINFO entry for TA_F"):
        read_daily(path)


def test_missing_member_raises(rewrite_archive, tmp_path):
    path = rewrite_archive(CVN, tmp_path / "a.zip", "_FLUXMET_DD_", lambda _: None)
    with pytest.raises(ProviderError, match="_FLUXMET_DD_"):
        read_daily(path)


def test_not_a_zip_raises(tmp_path):
    path = tmp_path / "a.zip"
    path.write_text("not a zip")
    with pytest.raises(ProviderError, match="not a ZIP"):
        read_daily(path)
