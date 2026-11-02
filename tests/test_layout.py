"""Checks the import rules in CONTRIBUTING.md."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[1] / "src" / "conduit_data"
MODULES = sorted(SRC.rglob("*.py"))

# Imported only through `conduit_data._extras.require`, never at module level.
EXTRAS = {"httpx", "typer"}
# The CLI is only imported once `main` has checked typer is installed.
EXTRAS_ALLOWED_IN = {SRC / "cli" / "app.py", SRC / "cli" / "cosmos.py"}


def _is_type_checking_block(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
    )


def _walk(node: ast.AST):
    # Imports under `if TYPE_CHECKING:` never run, so they do not count.
    yield node
    for child in ast.iter_child_nodes(node):
        if not _is_type_checking_block(child):
            yield from _walk(child)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in _walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _id(path: Path) -> str:
    return str(path.relative_to(SRC))


@pytest.mark.parametrize("path", MODULES, ids=_id)
def test_nothing_imports_conduit(path):
    assert "conduit" not in _imports(path)


@pytest.mark.parametrize(
    "path",
    [p for p in MODULES if p.stem in {"fetch", "standardise"}],
    ids=_id,
)
def test_fetch_and_standardise_need_no_contracts(path):
    assert not _imports(path) & {"xarray_annotated", "hamilton"}


@pytest.mark.parametrize(
    "path", [p for p in MODULES if p not in EXTRAS_ALLOWED_IN], ids=_id
)
def test_extras_are_imported_lazily(path):
    assert not _imports(path) & EXTRAS


def test_there_are_fetch_and_standardise_modules():
    stems = {p.stem for p in MODULES}
    assert {"fetch", "standardise"} <= stems
