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
    assert set(_graph.DARK_COLOURS) == set(_graph.ACTIONS)


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


def test_run_raises_the_node_error_quietly(caplog):
    # `archive_paths` raises inside the graph; Hamilton would log it too.
    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError, match="no ICOS"):
        icos_standardise.standardise([])
    assert not [r for r in caplog.records if r.name.startswith("hamilton")]
    assert not logging.getLogger("hamilton.driver").disabled


def _render_graphs():
    pytest.importorskip("dotdoc")
    return runpy.run_path(
        str(Path(__file__).parents[1] / "scripts" / "render_graphs.py")
    )


def test_digraph_fills_links_and_explains_each_node(nodes):
    source = _render_graphs()["digraph"](icos_standardise.MODULES).source
    for node in nodes:
        fn = node.originating_functions[0]
        url = f'URL="autoref:{fn.__module__}.{fn.__qualname__}"'
        assert url in source, node.name
    assert f'fillcolor="{_graph.COLOURS["interprets"]}"' in source
    assert 'tooltip="interprets: Describe each column by its first BIFVARINFO' in source


def test_digraph_legend_names_each_action_without_links():
    source = _render_graphs()["digraph"](icos_standardise.MODULES).source
    legend = source[source.index("subgraph cluster__legend") :]
    legend = legend[: legend.index("}")]
    for action in _graph.ACTIONS:
        assert f"{action} [" in legend, action
    assert "URL=" not in legend
    assert "tooltip=" not in legend


@pytest.mark.skipif(shutil.which("dot") is None, reason="needs Graphviz's dot")
def test_docs_fragment_has_a_key_and_a_preview_per_node(nodes):
    fragment = _render_graphs()["fragment"](icos_standardise.MODULES)
    assert fragment.count("data-preview") == len(nodes)
    assert fragment.count("<autoref ") == len(nodes)
    assert "\n\n" not in fragment.strip()
    light, dark = _graph.COLOURS["interprets"], _graph.DARK_COLOURS["interprets"]
    legend_and_fills = fragment.count(f"light-dark({light},{dark})")
    assert legend_and_fills == 1 + sum(n.tags["action"] == "interprets" for n in nodes)
