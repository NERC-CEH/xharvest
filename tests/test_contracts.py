"""Checks every connector's standardised output against the shared rules.

Add a connector to ``CONNECTORS`` with its `to_netcdf` function, a fixture of raw
provider output, its `VARIABLES` contract types, and its node module, if it has one. The checks run on the netCDF
file as read back, since that is what catena reads.
"""

import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest
import xarray as xr
import xarray_annotated as xra
from xarray_annotated.units import assert_valid_unit, use_cf_units

from xharvest import cosmos
from xharvest.cosmos import nodes as cosmos_nodes
from xharvest.provenance import PROVENANCE_ATTRS


@dataclass
class Connector:
    name: str
    to_netcdf: Any
    fixture: str
    variables: dict[str, Any]
    nodes: ModuleType | None


CONNECTORS = [
    Connector("cosmos", cosmos.to_netcdf, "cosmos_raw", cosmos.VARIABLES, cosmos_nodes),
]

SRC = Path(__file__).parents[1] / "src" / "xharvest"


def test_every_provider_is_in_connectors():
    # A provider missing from CONNECTORS would skip every check below, silently.
    providers = {p.parent.name for p in SRC.glob("*/_fetch.py")}
    assert {c.name for c in CONNECTORS} == providers


@pytest.fixture(params=CONNECTORS, ids=lambda c: c.name)
def standardised(request, tmp_path) -> tuple[Connector, xr.Dataset]:
    connector = request.param
    raw = request.getfixturevalue(connector.fixture)
    path = connector.to_netcdf(raw, tmp_path / f"{connector.name}.nc")
    with xr.open_dataset(path) as ds:
        return connector, ds.load()


def _time_dims(ds: xr.Dataset) -> list[str]:
    return [
        str(d)
        for d in ds.dims
        if d in ds.coords and np.issubdtype(ds[d].dtype, np.datetime64)
    ]


def _node_functions(module: ModuleType):
    return [
        fn
        for name, fn in inspect.getmembers(module, inspect.isfunction)
        if fn.__module__ == module.__name__ and not name.startswith("_")
    ]


def _declared(hint: Any) -> xra.Declared:
    declared = xra.declaration_from_hint(hint)
    assert declared is not None, f"{hint} declares no contract"
    return declared


def test_one_datetime_dimension(standardised):
    _, ds = standardised
    assert len(_time_dims(ds)) <= 1


def test_indexes_are_unique(standardised):
    _, ds = standardised
    for name, index in ds.indexes.items():
        assert index.is_unique, f"{name} has repeated values"


def test_aggregated_values_have_time_bounds(standardised):
    _, ds = standardised
    aggregated = [
        name
        for name, var in ds.data_vars.items()
        if "time:" in var.attrs.get("cell_methods", "")
        and "time: point" not in var.attrs["cell_methods"]
    ]
    if not aggregated:
        pytest.skip("no variable aggregates over time")
    (time,) = _time_dims(ds)
    # Decoding moves CF `bounds` from attrs to encoding.
    bounds = ds[time].attrs.get("bounds") or ds[time].encoding.get("bounds")
    assert bounds, f"{time} has no bounds, but {aggregated[0]} aggregates over time"
    assert bounds in ds.variables


def test_every_variable_has_valid_units(standardised):
    use_cf_units()
    _, ds = standardised
    for name, var in ds.data_vars.items():
        assert "units" in var.attrs, name
        assert_valid_unit(var.attrs["units"], f"{name} units")


def test_provenance_attributes(standardised):
    _, ds = standardised
    for attr in PROVENANCE_ATTRS:
        assert ds.attrs.get(attr), attr


def test_variables_declares_every_standardised_variable(standardised):
    connector, ds = standardised
    assert set(connector.variables) == set(ds.data_vars)


def test_standardised_output_meets_variables(standardised):
    use_cf_units()
    connector, ds = standardised
    violations = [
        violation
        for name, hint in connector.variables.items()
        for violation in xra.declaration_violations(ds[name], _declared(hint), name)
    ]
    assert not violations


def test_node_inputs_match_variables(standardised):
    use_cf_units()
    connector, ds = standardised
    if connector.nodes is None:
        pytest.skip("no node module")
    functions = _node_functions(connector.nodes)
    assert functions
    nodes = {fn.__name__ for fn in functions}
    for fn in functions:
        declared, _ = xra.declarations_from_signature(fn)
        for param in inspect.signature(fn).parameters:
            assert param in ds or param in nodes, (
                f"{fn.__name__}({param}): neither a standardised variable nor a node"
            )
            if param in nodes:
                continue
            assert param in declared, f"{fn.__name__}({param}) declares no contract"
            schema = _declared(connector.variables[param])
            conflicts = xra.declaration_conflicts(declared[param], schema)
            assert not conflicts, f"{fn.__name__}({param}): {conflicts}"
            assert not xra.declaration_violations(ds[param], declared[param], param)
