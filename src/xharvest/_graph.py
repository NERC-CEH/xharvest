"""Build, run and draw the Hamilton graphs that standardise each provider's data.

Each connector's `standardise` is a graph built from modules of nodes (see ADR 2):
its own `_pipeline` module and any shared format module, such as `_fluxnet`. Every
node does one thing and says what kind of thing with an `action` tag, from
`ACTIONS`; the provider's documentation draws the graph coloured by it, each node
linked to its entry in the node reference.
"""

import inspect
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import TYPE_CHECKING, Any

from hamilton import driver

if TYPE_CHECKING:
    import graphviz

ACTIONS = {
    "reads": "parses provider files without changing what they say",
    "selects": "keeps some of what was read and drops the rest",
    "checks": "raises if the data break an expectation, else passes them on",
    "decodes": "changes values as the provider specifies",
    "reshapes": "rearranges values without changing them",
    "annotates": "adds or rewrites attributes and coordinates, not values",
    "interprets": "a judgement the provider does not state",
}
"""The `action` tag every standardisation node carries, and what each means."""

COLOURS = {
    "reads": "#d6e4f0",
    "selects": "#e4dcef",
    "checks": "#d9ead3",
    "decodes": "#fde9c4",
    "reshapes": "#eeeeee",
    "annotates": "#fff7d1",
    "interprets": "#f4b6a6",
}
"""Fill colour of each action in the rendered graph; judgements stand out."""

# Hamilton logs a traceback, and an invitation to its Slack, when a node raises.
# The exception itself reaches the caller unchanged, so these are only noise.
_NOISY_LOGGERS = ("hamilton.driver", "hamilton.execution.graph_functions")


@contextmanager
def _quiet() -> Iterator[None]:
    loggers = [logging.getLogger(name) for name in _NOISY_LOGGERS]
    previous = [logger.disabled for logger in loggers]
    for logger in loggers:
        logger.disabled = True
    try:
        yield
    finally:
        for logger, was in zip(loggers, previous, strict=True):
            logger.disabled = was


def build(*modules: ModuleType) -> driver.Driver:
    """Build the graph of the nodes in `modules`."""
    return driver.Builder().with_modules(*modules).build()


def run(modules: tuple[ModuleType, ...], output: str, **inputs: Any) -> Any:
    """Run a graph to compute `output`, raising a node's exception unchanged."""
    with _quiet():
        return build(*modules).execute([output], inputs=inputs)[output]


def _summary(fn: Callable[..., Any]) -> str:
    """The first paragraph of `fn`'s docstring, on one line."""
    doc = inspect.getdoc(fn) or ""
    return " ".join(doc.split("\n\n", 1)[0].split())


def anchor(fn: Callable[..., Any]) -> str:
    """The page anchor mkdocstrings gives a node's documentation entry."""
    return f"#{fn.__module__}.{fn.__name__}"


def _style(*, node, node_class: str) -> tuple[dict[str, str], str, str | None]:
    """Fill a node by its action; link it to its docs entry; give it a tooltip."""
    action = node.tags.get("action")
    if action not in COLOURS:
        return {}, node_class, None
    style = {"style": "filled", "fillcolor": COLOURS[action]}
    functions = getattr(node, "originating_functions", None) or ()
    if functions:
        fn = functions[0]
        style["URL"] = anchor(fn)
        # Plain text: no Markdown backticks, and backslashes escaped for dot.
        summary = _summary(fn).replace("`", "").replace("\\", "\\\\")
        style["tooltip"] = f"{action}: {summary}"
    return style, node_class, action


def digraph(modules: tuple[ModuleType, ...]) -> "graphviz.Digraph":
    """Draw the graph, top to bottom, for a documentation page.

    Each node is filled by its `action`, links to its documentation entry on the
    same page (see `anchor`), and shows its action and docstring summary on
    hover. There is no legend: the page shows the actions next to the graph.
    Needs the `graphviz` package.
    """
    drawn = build(*modules).display_all_functions(
        custom_style_function=_style,
        show_schema=False,
        show_legend=False,
        orient="TB",
    )
    if drawn is None:
        raise ImportError("drawing a graph needs the `graphviz` package")
    return drawn
