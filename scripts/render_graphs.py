"""Draw each connector's standardisation graph for the docs.

Run through `just graphs`, which `just docs` runs before each build. Writes
`docs/providers/_graphs/<provider>.svg`, which is not committed. Needs the
`graphviz` package (in the `docs` group) and the Graphviz `dot` binary.
"""

from pathlib import Path

from xharvest import _graph
from xharvest.icos import _standardise as icos

GRAPHS = {"icos": icos.MODULES}
OUT = Path(__file__).parents[1] / "docs" / "providers" / "_graphs"


def main() -> None:
    """Render every graph to SVG."""
    OUT.mkdir(parents=True, exist_ok=True)
    for name, modules in GRAPHS.items():
        _graph.render(modules, OUT / f"{name}.svg")


if __name__ == "__main__":
    main()
