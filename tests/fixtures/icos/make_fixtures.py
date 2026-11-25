"""Regenerate the ICOS test fixtures from the live ICOS Carbon Portal.

Run by hand, from the repository root, when the fixtures need refreshing:

    uv run python tests/fixtures/icos/make_fixtures.py

It downloads each station's whole ETC L2 archive with `xharvest.icos.fetch` (85 and
74 MB), then writes a trimmed copy under the same name, holding only what
`xharvest.icos.standardise` reads:

- the ancillary file, cut to the groups standardise keeps, and for UK-AMo to the
  entries dated 2023;
- the station BIF, cut to its header, location, land cover and UTC offset (team
  members' contact details are left out);
- `BIF_Ancillary_Variables.csv`, the variable dictionary, whole.

The sidecar is the one `fetch` wrote, so its SHA-256 is that of the whole archive,
not of the trimmed copy. The stations are chosen so the fixtures cover what the
tests rely on:

- UK-AMo, a peat bog, has LAI, biomass and canopy height but no soil groups;
- DE-Har, a forest, has every group kept, including soil texture and organic
  carbon stocks.

It also saves the portal's station list, cut to these stations, as
`stations.json`.
"""

import csv
import io
import json
import re
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import httpx

from xharvest.icos import fetch
from xharvest.icos._fetch import SPARQL_URL, STATIONS_QUERY
from xharvest.icos._pipeline import GROUPS
from xharvest.provenance import sidecar_path

HERE = Path(__file__).parent
STATIONS = {"UK-AMo": "2023", "DE-Har": None}
"""Each station, and the year its entries are cut to, if any."""

SITE_GROUPS = {"GRP_HEADER", "GRP_LOCATION", "GRP_IGBP", "GRP_UTC_OFFSET"}


def _rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def _write(header: list[str], rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n", quoting=csv.QUOTE_ALL)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _trim_ancillary(text: str, year: str | None) -> str:
    header, rows = _rows(text)
    kept_groups = {f"GRP_{group}" for group in GROUPS}
    entries: dict[tuple[str, str], list[list[str]]] = defaultdict(list)
    for row in rows:
        if row[2] in kept_groups:
            entries[row[2], row[1]].append(row)

    def in_year(entry: list[list[str]]) -> bool:
        dates = [r[4] for r in entry if re.search(r"_DATE(_START)?$", r[3])]
        return year is None or any(d.startswith(year) for d in dates)

    kept = [row for entry in entries.values() if in_year(entry) for row in entry]
    return _write(header, kept)


def _trim_site(text: str) -> str:
    header, rows = _rows(text)
    return _write(header, [row for row in rows if row[2] in SITE_GROUPS])


def _trimmed(source: Path, dest: Path, year: str | None) -> None:
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(dest, "w") as out:
        for info in src.infolist():
            name = info.filename
            raw = src.read(info)
            if re.search(r"_ANCILLARY_", name):
                raw = _trim_ancillary(raw.decode("utf-8"), year).encode("utf-8")
            elif re.search(r"_SITEINFO_", name):
                raw = _trim_site(raw.decode("utf-8")).encode("utf-8")
            elif name != "BIF_Ancillary_Variables.csv":
                continue
            # Keep the source's timestamps, so the output is byte-identical
            # when the source is.
            member = zipfile.ZipInfo(name, date_time=info.date_time)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = info.external_attr
            out.writestr(member, raw)


def main() -> None:
    """Fetch the station archives, trim them, and save the station list."""
    for old in HERE.glob("*.zip"):
        old.unlink()
        sidecar_path(old).unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for station, year in STATIONS.items():
            (path,) = fetch(station, tmp)
            _trimmed(path, HERE / path.name, year)
            sidecar = sidecar_path(path)
            sidecar_path(HERE / path.name).write_bytes(sidecar.read_bytes())

    response = httpx.post(
        SPARQL_URL,
        data={"query": STATIONS_QUERY},
        headers={"Accept": "application/sparql-results+json"},
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()
    body["results"]["bindings"] = [
        b for b in body["results"]["bindings"] if b["stationId"]["value"] in STATIONS
    ]
    (HERE / "stations.json").write_text(json.dumps(body, indent=1) + "\n")


if __name__ == "__main__":
    main()
