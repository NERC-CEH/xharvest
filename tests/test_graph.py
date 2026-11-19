"""Checks the rules in ADR 2 for every connector's standardisation graph."""

import logging
import runpy
import shutil
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from xharvest import _graph
from xharvest.icos import _standardise as icos_standardise

GRAPHS = {"icos": icos_standardise.MODULES}


def _nodes(modules):
    dr = _graph.build(*modules)
    inputs = {v.name for v in dr.list_available_variables() if v.is_external_input}
    return [v for v in dr.list_available_variables() if v.name not in inputs]


@pytest.fixture(params=GRAPHS, ids=str)
def nodes(request):
    return _nodes(GRAPHS[request.param])


def test_every_node_has_a_docstring(nodes):
    assert [n.name for n in nodes if not n.documentation.strip()] == []


def test_every_node_has_a_known_action(nodes):
    unknown = {n.name: n.tags.get("action") for n in nodes}
    assert {k: v for k, v in unknown.items() if v not in _graph.ACTIONS} == {}


def test_every_pipeline_is_in_graphs():
    # A pipeline missing here would skip every check above, silently.
    src = Path(__file__).parents[1] / "src" / "xharvest"
    providers = {p.parent.name for p in src.glob("*/_pipeline.py")}
    assert set(GRAPHS) == providers
    script = Path(__file__).parents[1] / "scripts" / "render_graphs.py"
    assert set(runpy.run_path(str(script))["GRAPHS"]) == providers


def test_every_action_has_a_colour():
    assert set(_graph.COLOURS) == set(_graph.ACTIONS)


@pytest.mark.parametrize("name", GRAPHS)
def test_the_graph_has_one_input_and_ends_in_dataset(name):
    dr = _graph.build(*GRAPHS[name])
    inputs = [v.name for v in dr.list_available_variables() if v.is_external_input]
    assert inputs == ["paths"]
    assert "dataset" in {v.name for v in dr.list_available_variables()}


def test_pipeline_modules_are_not_catena_modules():
    registered = {ep.value for ep in entry_points(group="catena.modules")}
    pipelines = {m.__name__ for modules in GRAPHS.values() for m in modules}
    assert not registered & pipelines


def test_style_fills_nodes_by_action(nodes):
    class Node:
        def __init__(self, action):
            self.tags = {"action": action}

    style, node_class, legend = _graph._style(
        node=Node("interprets"), node_class="function"
    )
    assert style["fillcolor"] == _graph.COLOURS["interprets"]
    assert (node_class, legend) == ("function", "interprets")
    assert _graph._style(node=Node(None), node_class="input") == ({}, "input", None)


def test_run_raises_the_node_error_quietly(caplog):
    # `archive_paths` raises inside the graph; Hamilton would log it too.
    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError, match="no ICOS"):
        icos_standardise.standardise([])
    assert not [r for r in caplog.records if r.name.startswith("hamilton")]
    assert not logging.getLogger("hamilton.driver").disabled


@pytest.mark.skipif(shutil.which("dot") is None, reason="needs Graphviz's dot")
def test_render_writes_svg(tmp_path):
    pytest.importorskip("graphviz")
    _graph.render(icos_standardise.MODULES, tmp_path / "icos.svg")
    svg = (tmp_path / "icos.svg").read_text()
    assert _graph.COLOURS["interprets"] in svg
    assert "checked_flags" in svg
