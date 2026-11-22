"""Checks the provider pages against the rules in `docs/adding-a-connector.md`."""

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src" / "xharvest"
DOCS = ROOT / "docs"

PAGES = {
    "cosmos": ["providers/cosmos-uk.md"],
    "icos": ["providers/icos.md"],
}
"""Each connector's provider pages, relative to `docs/`."""

CONNECTORS = sorted(p.parent.name for p in SRC.glob("*/_fetch.py"))


def test_every_connector_has_pages():
    assert sorted(PAGES) == CONNECTORS


def _documented(name: str, connector: str, text: str) -> bool:
    # Rendered from its docstring, or named in code: `fetch`, `icos.CarbonFlux`.
    directive = rf"^::: xharvest\.{connector}\.{re.escape(name)}$"
    named = rf"`(?:{connector}\.)?{re.escape(name)}`"
    return any(re.search(p, text, re.MULTILINE) for p in (directive, named))


@pytest.mark.parametrize("connector", CONNECTORS)
def test_every_public_name_is_documented(connector):
    module = importlib.import_module(f"xharvest.{connector}")
    text = "\n".join((DOCS / page).read_text() for page in PAGES[connector])
    missing = [
        name for name in module.__all__ if not _documented(name, connector, text)
    ]
    assert not missing, f"not on the {connector} provider page: {missing}"
