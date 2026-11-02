import json

import numpy as np
import pytest
import xarray as xr

from xharvest.cosmos import standardise, to_netcdf
from xharvest.cosmos.standardise import _duration
from xharvest.errors import ProviderError
from xharvest.provenance import PROVENANCE_ATTRS, sidecar_path


@pytest.fixture
def ds(cosmos_raw):
    return standardise(cosmos_raw)


def test_dims_and_coords(ds):
    assert dict(ds.sizes) == {"time": 17, "site": 2, "nv": 2}
    assert list(ds.site.values) == ["ALIC1", "MOORH"]
    assert ds.time.dtype == np.dtype("datetime64[ns]")
    for name in ds.data_vars:
        assert ds[name].dims == ("time", "site")


def test_site_names(ds):
    assert list(ds.site_name.values) == ["Alice Holt", "Moor House"]
    assert ds.site_name.dims == ("site",)


def test_requires_site_names_in_the_sidecar(cosmos_raw):
    sidecar = sidecar_path(cosmos_raw[0])
    body = json.loads(sidecar.read_text())
    del body["metadata"]
    sidecar.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="no name for site ALIC1"):
        standardise(cosmos_raw)


def test_lat_lon_and_altitude(ds):
    alic = ds.sel(site="ALIC1")
    assert alic.lat.item() == pytest.approx(51.153551)
    assert alic.lon.item() == pytest.approx(-0.858232)
    assert ds.altitude.attrs["units"] == "m"


def test_units_are_the_apis_own(ds, cosmos_raw):
    parameters = json.loads(cosmos_raw[0].read_text())["parameters"]
    for name, parameter in parameters.items():
        assert ds[name].attrs["units"] == parameter["unit"]["symbol"]["value"]
        assert ds[name].attrs["long_name"] == parameter["label"]


def test_values_are_unchanged_and_nulls_become_nan(ds, cosmos_raw):
    moorh = next(p for p in cosmos_raw if p.name.startswith("MOORH"))
    coverage = json.loads(moorh.read_text())["coverages"][0]
    raw = coverage["ranges"]["cosmos_vwc"]["values"]
    got = ds.cosmos_vwc.sel(site="MOORH").dropna("time").values
    assert list(got) == [v for v in raw if v is not None]
    assert ds.tdt3_vwc.sel(site="ALIC1").isnull().all()


def test_integer_snow_becomes_float(ds):
    assert ds.snow.dtype == np.float64
    assert set(np.unique(ds.snow.sel(site="MOORH").dropna("time"))) == {0.0, 1.0}


def test_sites_are_outer_joined_on_time(ds):
    assert str(ds.time[0].values)[:10] == "2025-01-01"
    assert str(ds.time[-1].values)[:10] == "2025-01-17"
    assert ds.ta.sel(site="ALIC1", time="2025-01-01").isnull()
    assert ds.ta.sel(site="MOORH", time="2025-01-17").isnull()


def test_cell_methods(ds):
    assert ds.cosmos_vwc.attrs["cell_methods"] == "time: mean"
    assert ds.precip.attrs["cell_methods"] == "time: sum"
    assert ds.snow.attrs["cell_methods"] == "time: point"
    assert ds.albedo.attrs["cell_methods"] == (
        "time: mean (comment: over PT4H within each period)"
    )


def test_daily_bounds_start_at_the_stamp(ds):
    assert ds.time.attrs["bounds"] == "time_bounds"
    first = ds.time_bounds.isel(time=0).values
    assert (first[1] - first[0]) == np.timedelta64(1, "D")
    assert first[0] == ds.time.values[0]


@pytest.mark.parametrize(
    ("period", "hours"),
    [("PT1D", 24), ("P1D", 24), ("-PT30M", -0.5), ("PT4H", 4)],
)
def test_duration(period, hours):
    assert _duration(period).total_seconds() == hours * 3600


@pytest.mark.parametrize("period", ["", "P", "1D", "PTxH"])
def test_bad_duration(period):
    with pytest.raises(ProviderError, match="cannot read"):
        _duration(period)


def test_half_hourly_bounds_end_at_the_stamp(cosmos_raw):
    path = cosmos_raw[0]
    body = json.loads(path.read_text())
    for parameter in body["parameters"].values():
        parameter["measurementType"]["period"] = "-PT30M"
    path.write_text(json.dumps(body))
    ds = standardise([path])
    first = ds.time_bounds.isel(time=0).values
    assert first[1] == ds.time.values[0]
    assert (first[1] - first[0]) == np.timedelta64(30, "m")


def test_provenance(ds):
    for attr in PROVENANCE_ATTRS:
        assert ds.attrs[attr]
    assert "open-government-licence" in ds.attrs["license"]
    history = ds.attrs["history"].splitlines()
    assert len(history) == 3
    assert "retrieved https://cosmos-api.ceh.ac.uk" in history[0]
    assert "datetime=" in history[0]
    assert "standardised" in history[-1]


def test_sidecars_and_non_json_files_in_a_glob(cosmos_raw, tmp_path):
    every_file = sorted(tmp_path.iterdir())
    assert len(every_file) == 4
    assert standardise(every_file).sizes["site"] == 2
    (tmp_path / "notes.json").write_bytes(b"\x89PNG")
    with pytest.raises(ProviderError, match="not a COSMOS-UK JSON response"):
        standardise(tmp_path.iterdir())


def test_rejects_other_json(tmp_path):
    path = tmp_path / "other.json"
    path.write_text('{"type": "FeatureCollection"}')
    with pytest.raises(ProviderError, match="not a COSMOS-UK point-series"):
        standardise([path])


def test_requires_a_sidecar(cosmos_raw):
    sidecar_path(cosmos_raw[0]).unlink()
    with pytest.raises(FileNotFoundError, match="no provenance sidecar"):
        standardise(cosmos_raw)


def test_requires_some_files():
    with pytest.raises(ValueError, match="no COSMOS-UK files"):
        standardise([])


def test_rejects_mixed_collections(cosmos_raw):
    path = cosmos_raw[0]
    body = json.loads(path.read_text())
    for parameter in body["parameters"].values():
        parameter["measurementType"]["period"] = "-PT30M"
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="mix COSMOS-UK collections"):
        standardise(cosmos_raw)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p.pop("unit"), "has no units"),
        (
            lambda p: p["measurementType"].update(method="median"),
            "unknown COSMOS-UK aggregation",
        ),
    ],
)
def test_unreadable_parameter_metadata(cosmos_raw, change, message):
    path = cosmos_raw[0]
    body = json.loads(path.read_text())
    change(body["parameters"]["ta"])
    path.write_text(json.dumps(body))
    with pytest.raises(ProviderError, match=message):
        standardise([path])


def test_no_aggregated_parameters(cosmos_raw):
    path = cosmos_raw[0]
    body = json.loads(path.read_text())
    body["parameters"] = {"snow": body["parameters"]["snow"]}
    body["coverages"][0]["ranges"] = {"snow": body["coverages"][0]["ranges"]["snow"]}
    path.write_text(json.dumps(body))
    with pytest.raises(ProviderError, match="infer a period"):
        standardise([path])


def test_netcdf_round_trip(cosmos_raw, tmp_path):
    out = to_netcdf(cosmos_raw, tmp_path / "out" / "cosmos.nc")
    expected = standardise(cosmos_raw)
    with xr.open_dataset(out) as got:
        xr.testing.assert_identical(got.drop_attrs(), expected.drop_attrs())
        assert got.cosmos_vwc.attrs["units"] == "%"
        assert got.time.encoding["units"] == got.time_bounds.encoding["units"]
        assert "time_bounds" in got.coords
