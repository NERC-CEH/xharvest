import re
import shutil

import numpy as np
import pytest
import xarray as xr

from xharvest.errors import ProviderError
from xharvest.fluxnet import VARIABLES, standardise, to_netcdf
from xharvest.fluxnet import _archive as fx
from xharvest.provenance import PROVENANCE_ATTRS, sidecar_path


def _by_site(paths):
    return {p.name.split("_")[1]: p for p in paths}


def _copy_with_sidecar(path, dest):
    shutil.copy(path, dest)
    shutil.copy(sidecar_path(path), sidecar_path(dest))
    return dest


def test_dims_and_variables(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    assert set(ds.site.values) == {"UK-Ags", "UK-Cvn"}
    assert set(ds.data_vars) == set(VARIABLES)
    assert ds.TA_F.dims == ("time", "site")
    assert ds.SWC_F_MDS.dims == ("time", "site", "depth")
    assert ds.TS_F_MDS_QC.dims == ("time", "site", "depth")


def test_time_is_the_union_of_the_sites_days(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    assert ds.time.values[0] == np.datetime64("2023-09-01")
    assert ds.time.values[-1] == np.datetime64("2023-09-21")
    assert len(ds.time) == 21
    cvn = ds.TA_F.sel(site="UK-Cvn")
    assert cvn.sel(time="2023-09-14").notnull()
    assert cvn.sel(time="2023-09-15").isnull()


def test_time_bounds_cover_one_day(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    assert ds.time.attrs["bounds"] == "time_bounds"
    bounds = ds.time_bounds.values
    np.testing.assert_array_equal(bounds[:, 0], ds.time.values)
    np.testing.assert_array_equal(bounds[:, 1] - bounds[:, 0], np.timedelta64(1, "D"))


def test_depth_is_the_union_of_the_sites_sensors(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    np.testing.assert_allclose(
        ds.depth.values, [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    )
    assert ds.depth.attrs["positive"] == "down"
    cvn = ds.SWC_F_MDS.sel(site="UK-Cvn", time="2023-09-05")
    ags = ds.SWC_F_MDS.sel(site="UK-Ags", time="2023-09-10")
    assert cvn.sel(depth=0.15).notnull()
    assert cvn.sel(depth=0.2).isnull()
    assert ags.sel(depth=0.2).notnull()
    assert ags.sel(depth=0.15).isnull()


def test_values_are_the_archives_own(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    path = _by_site(fluxnet_raw)["UK-Cvn"]
    columns = fx.tables(fx.raw_tables(fx.archive_texts([path])))[path].columns
    cvn = ds.sel(site="UK-Cvn", time=slice("2023-09-01", "2023-09-14"))
    np.testing.assert_array_equal(cvn.TA_F.values, columns["TA_F"])
    np.testing.assert_array_equal(cvn.NEE_VUT_REF.values, columns["NEE_VUT_REF"])
    # SWC_F_MDS_5 is the 0.25 m sensor at UK-Cvn.
    np.testing.assert_array_equal(
        cvn.SWC_F_MDS.sel(depth=0.25).values, columns["SWC_F_MDS_5"]
    )
    np.testing.assert_array_equal(
        cvn.SWC_F_MDS_QC.sel(depth=0.25).values, columns["SWC_F_MDS_5_QC"]
    )


def test_variable_attributes(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    assert ds.TA_F.attrs["units"] == "degC"
    assert ds.TA_F.attrs["provider_units"] == "deg C"
    assert ds.NEE_VUT_REF.attrs["units"] == "g m-2 d-1"
    assert ds.NEE_VUT_REF.attrs["provider_units"] == "gC m-2 d-1"
    assert ds.P_F.attrs["cell_methods"] == "time: mean"
    assert "cell_methods" not in ds.NEE_VUT_REF_JOINTUNC.attrs
    # Defined as daily means, but the data say otherwise.
    assert "cell_methods" not in ds.LE_CORR.attrs
    assert "cell_methods" not in ds.H_CORR.attrs
    assert "Precipitation" in ds.P_F.attrs["description"]


def test_qc_attributes_ignore_the_archives_mislabelling(fluxnet_raw):
    # BIFVARINFO gives SWC_F_MDS_<n>_QC the unit % and SWC_F_MDS's definition.
    ds = standardise(fluxnet_raw)
    attrs = ds.SWC_F_MDS_QC.attrs
    assert attrs["units"] == "1"
    assert attrs["description"].startswith("Quality flag for SWC_F_MDS")
    assert "provider_units" not in attrs
    assert "cell_methods" not in attrs
    values = ds.SWC_F_MDS_QC.values
    assert np.nanmin(values) >= 0
    assert np.nanmax(values) <= 1


def test_site_coordinates(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    cvn = ds.sel(site="UK-Cvn")
    assert cvn.site_name.item() == "Coveney"
    assert (cvn.lat.item(), cvn.lon.item()) == pytest.approx((52.43339, 0.162177))
    assert cvn.altitude.item() == pytest.approx(-0.67)
    assert cvn.utc_offset.item() == 0
    assert (cvn.igbp.item(), cvn.network.item()) == ("GRA", "EUF")


def test_global_attributes(fluxnet_raw):
    ds = standardise(fluxnet_raw)
    for attr in PROVENANCE_ATTRS:
        assert ds.attrs[attr]
    assert ds.attrs["license"] == "CC-BY-4.0"
    references = ds.attrs["references"].splitlines()
    assert len(references) == 2
    assert any("Coveney" in r for r in references)
    assert any("Anglesey" in r for r in references)
    assert ds.attrs["history"].count("retrieved https://data.icos-cp.eu/") == 2


def test_sidecars_among_the_paths_are_skipped(fluxnet_raw):
    paths = [*fluxnet_raw, *(sidecar_path(p) for p in fluxnet_raw)]
    assert set(standardise(paths).site.values) == {"UK-Ags", "UK-Cvn"}


def test_no_paths_raise():
    with pytest.raises(ValueError, match="no FLUXNET"):
        standardise([])


def test_missing_sidecar_raises(fluxnet_raw):
    sidecar_path(fluxnet_raw[0]).unlink()
    with pytest.raises(FileNotFoundError, match="sidecar"):
        standardise(fluxnet_raw)


def test_sites_with_different_utc_offsets_are_refused(
    fluxnet_raw, rewrite_archive, tmp_path
):
    ags = _by_site(fluxnet_raw)["UK-Ags"]
    (tmp_path / "x").mkdir()
    shifted = rewrite_archive(
        ags,
        tmp_path / "x" / ags.name,
        "_FLUXNET_BIF_",
        lambda t: re.sub(r"(GRP_UTC_OFFSET,UTC_OFFSET,)0", r"\g<1>1", t),
    )
    shutil.copy(sidecar_path(ags), sidecar_path(shifted))
    with pytest.raises(ValueError, match=r"UK-Cvn \(UTC\+0\), UK-Ags \(UTC\+1\)"):
        standardise([shifted, _by_site(fluxnet_raw)["UK-Cvn"]])


def test_an_unexpected_unit_raises(fluxnet_raw, rewrite_archive, tmp_path):
    cvn = _by_site(fluxnet_raw)["UK-Cvn"]
    (tmp_path / "x").mkdir()
    changed = rewrite_archive(
        cvn,
        tmp_path / "x" / cvn.name,
        "BIFVARINFO",
        lambda t: re.sub(
            r"(VAR_INFO_VARNAME,TA_F\n(?:.*\n)*?.*VAR_INFO_UNIT,)deg C", r"\1hPa", t
        ),
    )
    shutil.copy(sidecar_path(cvn), sidecar_path(changed))
    with pytest.raises(ProviderError, match="TA_F has unit 'hPa'"):
        standardise([changed])


def test_qc_outside_zero_to_one_raises(fluxnet_raw, rewrite_archive, tmp_path):
    cvn = _by_site(fluxnet_raw)["UK-Cvn"]
    (tmp_path / "x").mkdir()

    def scale_ta_f_qc(text):
        lines = text.splitlines(keepends=True)
        column = lines[0].strip().split(",").index("TA_F_QC")
        cells = lines[1].rstrip("\n").split(",")
        cells[column] = "48"
        lines[1] = ",".join(cells) + "\n"
        return "".join(lines)

    changed = rewrite_archive(
        cvn, tmp_path / "x" / cvn.name, "_FLUXMET_DD_", scale_ta_f_qc
    )
    shutil.copy(sidecar_path(cvn), sidecar_path(changed))
    with pytest.raises(ProviderError, match="TA_F_QC has values outside 0-1"):
        standardise([changed])


def test_overlapping_archives_of_one_site_are_joined(fluxnet_raw, tmp_path):
    cvn = _by_site(fluxnet_raw)["UK-Cvn"]
    copy = _copy_with_sidecar(cvn, tmp_path / "EUF_UK-Cvn_FLUXNET_copy.zip")
    ds = standardise([cvn, copy])
    assert list(ds.site.values) == ["UK-Cvn"]
    assert len(ds.time) == 14


def test_conflicting_archives_of_one_site_raise(fluxnet_raw, rewrite_archive, tmp_path):
    cvn = _by_site(fluxnet_raw)["UK-Cvn"]

    def change_first_ta_f(text):
        lines = text.splitlines(keepends=True)
        column = lines[0].strip().split(",").index("TA_F")
        cells = lines[1].rstrip("\n").split(",")
        cells[column] = "99.9"
        lines[1] = ",".join(cells) + "\n"
        return "".join(lines)

    revised = rewrite_archive(
        cvn, tmp_path / "EUF_UK-Cvn_revised.zip", "_FLUXMET_DD_", change_first_ta_f
    )
    shutil.copy(sidecar_path(cvn), sidecar_path(revised))
    with pytest.raises(ValueError, match="disagree where they overlap"):
        standardise([cvn, revised])


def test_to_netcdf_round_trips(fluxnet_raw, tmp_path):
    out = to_netcdf(fluxnet_raw, tmp_path / "out" / "fluxnet.nc")
    with xr.open_dataset(out) as ds:
        assert ds.SWC_F_MDS.dims == ("time", "site", "depth")
        assert ds.time.encoding["units"] == "minutes since 1970-01-01"
        np.testing.assert_array_equal(
            ds.time_bounds.values[:, 1] - ds.time_bounds.values[:, 0],
            np.timedelta64(1, "D"),
        )
