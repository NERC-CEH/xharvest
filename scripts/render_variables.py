"""Tabulate each connector's standardised variables for its overview page.

Run through `just variables`, which `just docs` runs before each build. Writes
`docs/providers/_variables/<provider>.md`, the table, and
`<provider>-dataset.md`, the standardised fixtures as xarray prints them, which
the page includes and which are not committed.

Both tables come from the committed fixtures, so the build needs no network and a
table changes only when the fixtures are regenerated:

- COSMOS-UK: every daily parameter the API describes, from the site list that
  `tests/fixtures/cosmos/make_fixtures.py` saves. `fetch` requests them all
  unless told otherwise.
- ICOS: the variables of the fixture archives, standardised, with the unit and
  description `standardise` writes.
"""

import json
import re
from pathlib import Path

import xarray as xr

from xharvest.cosmos import standardise as cosmos_standardise
from xharvest.icos import standardise as icos_standardise

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUT = ROOT / "docs" / "providers" / "_variables"

_MARKDOWN = re.compile(r"([\\`*_{}\[\]<>|^~#])")


def _text(value: str) -> str:
    """Escape provider text so markdown renders it as written."""
    return _MARKDOWN.sub(r"\\\1", " ".join(value.split()))


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = [f"| {' | '.join(header)} |", f"|{'---|' * len(header)}"]
    lines += [f"| {' | '.join(row)} |" for row in rows]
    return "\n".join(lines) + "\n"


def cosmos() -> str:
    """Every daily parameter the COSMOS-UK API describes."""
    locations = json.loads((FIXTURES / "cosmos" / "locations_1D.json").read_text())
    rows = []
    for name, parameter in sorted(locations["parameters"].items()):
        method = parameter["measurementType"]["method"]
        period = parameter["measurementType"]["period"]
        if period not in {"PT1D", "P1D"}:
            method += f" over {period.lstrip('-')}"
        rows.append(
            [
                f"`{name}`",
                f"`{parameter['unit']['symbol']['value']}`",
                method,
                _text(parameter["description"]),
            ]
        )
    return _table(["Name", "Unit", "Method", "Description"], rows)


def icos() -> str:
    """The variables `standardise` keeps from FLUXNET archives."""
    ds = icos_standardise(sorted((FIXTURES / "icos").glob("*.zip")))
    rows = []
    for name, variable in ds.data_vars.items():
        if str(name).endswith("_QC"):
            continue
        rows.append(
            [
                f"`{name}`",
                f"`{variable.attrs['units']}`",
                "on `depth`" if "depth" in variable.dims else "",
                "yes" if f"{name}_QC" in ds else "",
                _text(variable.attrs.get("description", "")),
            ]
        )
    return _table(["Name", "Unit", "Profile", "`_QC`", "Description"], rows)


def printed(ds: xr.Dataset) -> str:
    """The Dataset as `print` shows it, in a code block."""
    return f"```text\n{ds}\n```\n"


def main() -> None:
    """Write every provider's table and printed fixtures."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cosmos.md").write_text(cosmos())
    (OUT / "icos.md").write_text(icos())
    cosmos_raw = sorted((FIXTURES / "cosmos").glob("*_1D_*.json"))
    (OUT / "cosmos-dataset.md").write_text(printed(cosmos_standardise(cosmos_raw)))
    icos_raw = sorted((FIXTURES / "icos").glob("*.zip"))
    (OUT / "icos-dataset.md").write_text(printed(icos_standardise(icos_raw)))


if __name__ == "__main__":
    main()
