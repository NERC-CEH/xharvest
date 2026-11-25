"""Checks the provider pages against the rules in `docs/adding-a-connector.md`."""

import importlib
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src" / "xharvest"
DOCS = ROOT / "docs"

PAGES = {
    "cosmos": "providers/cosmos-uk",
    "fluxnet": "providers/fluxnet",
    "icos": "providers/icos",
}
"""Each connector's directory of provider pages, relative to `docs/`."""

SECTIONS = ["index.md", "data.md", "standardise.md", "catena.md", "reference.md"]
"""The pages every provider has, in nav order."""

CONNECTORS = sorted(p.parent.name for p in SRC.glob("*/_fetch.py"))


def _nav_pages(entries) -> list[str]:
    pages = []
    for entry in entries:
        for value in entry.values() if isinstance(entry, dict) else [entry]:
            pages += _nav_pages(value) if isinstance(value, list) else [value]
    return pages


def test_every_connector_has_pages():
    assert sorted(PAGES) == CONNECTORS


@pytest.mark.parametrize("connector", CONNECTORS)
def test_every_connector_has_the_same_pages_in_the_nav(connector):
    directory = DOCS / PAGES[connector]
    assert sorted(p.name for p in directory.glob("*.md")) == sorted(SECTIONS)
    nav = _nav_pages(
        tomllib.loads((ROOT / "zensical.toml").read_text())["project"]["nav"]
    )
    assert [p for p in nav if p.startswith(f"{PAGES[connector]}/")] == [
        f"{PAGES[connector]}/{page}" for page in SECTIONS
    ]


def _documented(name: str, connector: str, text: str) -> bool:
    # Rendered from its docstring, or named in code: `fetch`, `fluxnet.CarbonFlux`.
    directive = rf"^::: xharvest\.{connector}\.{re.escape(name)}$"
    named = rf"`(?:{connector}\.)?{re.escape(name)}`"
    return any(re.search(p, text, re.MULTILINE) for p in (directive, named))


@pytest.mark.parametrize("connector", CONNECTORS)
def test_every_public_name_is_documented(connector):
    module = importlib.import_module(f"xharvest.{connector}")
    pages = sorted((DOCS / PAGES[connector]).glob("*.md"))
    text = "\n".join(page.read_text() for page in pages)
    missing = [
        name for name in module.__all__ if not _documented(name, connector, text)
    ]
    assert not missing, f"not on the {connector} provider page: {missing}"
