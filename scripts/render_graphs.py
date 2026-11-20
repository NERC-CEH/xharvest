"""Draw each connector's standardisation graph for its provider page.

Run through `just graphs`, which `just docs` runs before each build. Writes
`docs/providers/_graphs/<provider>.html`, which the page includes and which is
not committed. Needs the `docs` dependency group and the Graphviz `dot` binary.

The fragment holds the graph, drawn with dotdoc: each node is filled by its
action, with Hamilton's legend as the key, its name links to its entry in the
page's node reference and previews it on hover, its tooltip gives its action and
docstring summary, and buttons above the graph zoom it and expand it to the
window. Fills switch to `_graph.DARK_COLOURS` with the theme's dark scheme.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import graphviz
from dotdoc import graph_html
from dotdoc.hamilton import (
    clean_legend,
    compose_styles,
    fill_by_tag,
    link_style,
    summary,
    tooltip_style,
)
from hamilton.graph_types import HamiltonNode

from xharvest import _graph
from xharvest.cosmos import _standardise as cosmos
from xharvest.icos import _standardise as icos

GRAPHS = {"cosmos": cosmos.MODULES, "icos": icos.MODULES}
OUT = Path(__file__).parents[1] / "docs" / "providers" / "_graphs"

# Each light fill to its dark counterpart; Hamilton fills input nodes white.
DARK = {_graph.COLOURS[a]: _graph.DARK_COLOURS[a] for a in _graph.ACTIONS}
DARK["#ffffff"] = "transparent"


def _tooltip(node: HamiltonNode, fn: Callable | None) -> str | None:
    """A node's action and the first paragraph of its docstring."""
    action = node.tags.get("action")
    if fn is None or action not in _graph.ACTIONS:
        return None
    return f"{action}: {summary(fn)}"


def digraph(modules: tuple[ModuleType, ...]) -> graphviz.Digraph:
    """Draw the graph top to bottom, each node styled as the module docstring says."""
    dr = _graph.build(*modules)
    drawn = dr.display_all_functions(
        custom_style_function=compose_styles(
            fill_by_tag("action", _graph.COLOURS),
            tooltip_style(dr, _tooltip),
            link_style(dr),
        ),
        show_schema=False,
        orient="TB",
    )
    assert drawn is not None, "Hamilton returns no drawing without `graphviz`"
    return clean_legend(drawn)


def fragment(modules: tuple[ModuleType, ...]) -> str:
    """The HTML a provider page includes, on one line."""
    return graph_html(digraph(modules), controls=True, dark=DARK) + "\n"


def main() -> None:
    """Write every provider's fragment."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, modules in GRAPHS.items():
        (OUT / f"{name}.html").write_text(fragment(modules))


if __name__ == "__main__":
    main()
