"""Checks every connector's standardised output against the shared rules.

Add a connector to ``CONNECTORS`` with its standardise function, a fixture of raw
provider output, and its node module, if it has one.
"""

import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import numpy as np
import pytest
import xarray as xr
from xarray_annotated.temporal import check_freq, freq_from_signature
from xarray_annotated.units import (
    assert_valid_unit,
    units_compatible,
    units_from_signature,
    use_cf_units,
)

from conduit_data import cosmos
from conduit_data.cosmos import nodes as cosmos_nodes
from conduit_data.provenance import PROVENANCE_ATTRS


@dataclass
class Connector:
    name: str
    standardise: Any
    fixture: str
    nodes: ModuleType | None


CONNECTORS = [
    Connector("cosmos", cosmos.standardise, "cosmos_raw", cosmos_nodes),
]


@pytest.fixture(params=CONNECTORS, ids=lambda c: c.name)
def standardised(request) -> tuple[Connector, xr.Dataset]:
    connector = request.param
    raw = request.getfixturevalue(connector.fixture)
    return connector, connector.standardise(raw)


def _node_functions(module: ModuleType):
    return [
        fn
        for name, fn in inspect.getmembers(module, inspect.isfunction)
        if fn.__module__ == module.__name__ and not name.startswith("_")
    ]


def test_one_datetime_dimension(standardised):
    _, ds = standardised
    time_dims = [
        d
        for d in ds.dims
        if d in ds.coords and np.issubdtype(ds[d].dtype, np.datetime64)
    ]
    assert len(time_dims) <= 1


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


def test_node_inputs_match_standardised_output(standardised):
    use_cf_units()
    connector, ds = standardised
    if connector.nodes is None:
        pytest.skip("no node module")
    functions = _node_functions(connector.nodes)
    assert functions
    for fn in functions:
        units, _ = units_from_signature(fn)
        freqs, _ = freq_from_signature(fn)
        for param in inspect.signature(fn).parameters:
            if param not in ds:
                continue
            if param in units:
                assert units_compatible(ds[param].attrs["units"], units[param]), (
                    f"{fn.__name__}({param}): {ds[param].attrs['units']} vs "
                    f"{units[param]}"
                )
            if param in freqs:
                for site in ds[param].transpose("site", ...):
                    check_freq(site, freqs[param], param, on_mismatch="error")
