"""Draw each connector's standardisation graph for its provider page.

Run through `just graphs`, which `just docs` runs before each build. Writes
`docs/providers/_graphs/<provider>.html`, which the page includes and which is
not committed. Needs the `graphviz` package and the Graphviz `dot` binary.

The fragment holds the graph as inline SVG, through catena's `graph_html`, so
each node links to its entry in the page's node reference and previews it on
hover; a key to the actions; and a button that shows the graph full screen
(`docs/_static/js/graph.js`).
"""

import html
from pathlib import Path

from catena.graph import graph_html

from xharvest import _graph
from xharvest.icos import _standardise as icos

GRAPHS = {"icos": icos.MODULES}
OUT = Path(__file__).parents[1] / "docs" / "providers" / "_graphs"


def key() -> str:
    """A key to the actions, each with its colour and meaning."""
    items = "".join(
        f'<li><span class="xh-swatch" style="background:{_graph.COLOURS[action]}">'
        f"</span><code>{action}</code> {html.escape(meaning)}</li>"
        for action, meaning in _graph.ACTIONS.items()
    )
    return f'<ul class="xh-graph-key">{items}</ul>'


def fragment(modules) -> str:
    """The HTML a provider page includes: button, key and graph, on one line."""
    button = (
        '<button type="button" class="xh-graph-fullscreen md-button" hidden>'
        "Full screen</button>"
    )
    return (
        f'<div class="xh-graph">{button}{key()}'
        f"{graph_html(_graph.digraph(modules))}</div>\n"
    )


def main() -> None:
    """Write every provider's fragment."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, modules in GRAPHS.items():
        (OUT / f"{name}.html").write_text(fragment(modules))


if __name__ == "__main__":
    main()
