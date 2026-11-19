"""Build, run and draw the Hamilton graphs that standardise each provider's data.

Each connector's `standardise` is a graph built from modules of nodes (see ADR 2):
its own `_pipeline` module and any shared format module, such as `_fluxnet`. Every
node does one thing and says what kind of thing with an `action` tag, from
`ACTIONS`; the provider's documentation renders the graph coloured by it.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from os import PathLike
from types import ModuleType
from typing import Any

from hamilton import driver

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


def _style(*, node, node_class: str) -> tuple[dict[str, str], str, str | None]:
    action = node.tags.get("action")
    if action not in COLOURS:
        return {}, node_class, None
    return {"style": "filled", "fillcolor": COLOURS[action]}, node_class, action


def render(modules: tuple[ModuleType, ...], out: str | PathLike) -> None:
    """Draw the graph to the SVG file `out`, each node filled by its `action`.

    Needs the `graphviz` package and the Graphviz `dot` binary.
    """
    build(*modules).display_all_functions(
        str(out),
        render_kwargs={"format": "svg"},
        custom_style_function=_style,
        show_schema=False,
    )
