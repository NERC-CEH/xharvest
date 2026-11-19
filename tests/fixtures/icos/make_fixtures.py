"""Regenerate the ICOS test fixtures from the live ICOS Carbon Portal.

Run by hand, from the repository root, when the fixtures need refreshing:

    uv run python tests/fixtures/icos/make_fixtures.py

It downloads each site's whole archive with `xharvest.icos.fetch` (27 and 38 MB),
then writes a trimmed copy under the same name, holding only what
`xharvest.icos.standardise` reads:

- the daily data file, cut to the site's window below;
- `BIFVARINFO_DD`, whole;
- the site BIF, cut to the groups standardise reads (team members' contact
  details are left out);
- the README and the data policy, whole.

The sidecar is the one `fetch` wrote, so its SHA-256 is that of the whole archive,
not of the trimmed copy. The windows are chosen so the fixtures cover what the
tests rely on:

- the windows differ, so combining the sites pads each with NaN;
- the sites' soil sensors are at different depths (UK-Cvn at 0.15 and 0.25 m,
  UK-Ags at 0.2 to 0.5 m), so the depth axis is a union.

It also saves the portal's site list, cut to these sites, as `sites.json`.
"""

import csv
import io
import json
import re
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import httpx

from xharvest.icos import fetch
from xharvest.icos._fetch import SITES_QUERY, SPARQL_URL
from xharvest.provenance import sidecar_path

HERE = Path(__file__).parent
SITES = {
    "UK-Cvn": (date(2023, 9, 1), date(2023, 9, 14)),
    "UK-Ags": (date(2023, 9, 8), date(2023, 9, 21)),
}
BIF_GROUPS = {
    "GRP_HEADER",
    "GRP_LOCATION",
    "GRP_UTC_OFFSET",
    "GRP_IGBP",
    "GRP_ONEFLUX",
}


def _trim_data(text: str, start: date, end: date) -> str:
    lines = text.splitlines(keepends=True)
    first, last = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    kept = [line for line in lines[1:] if first <= line[:8] <= last]
    return lines[0] + "".join(kept)


def _trim_bif(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(rows[0])
    writer.writerows(row for row in rows[1:] if row[2] in BIF_GROUPS)
    return out.getvalue()


def _trimmed(source: Path, dest: Path, start: date, end: date) -> None:
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(dest, "w") as out:
        for info in src.infolist():
            name = info.filename
            raw = src.read(info)
            if re.search(r"_FLUXMET_DD_", name):
                raw = _trim_data(raw.decode("ascii"), start, end).encode("ascii")
            elif re.search(r"_FLUXNET_BIF_", name):
                raw = _trim_bif(raw.decode("latin-1")).encode("latin-1")
            elif not re.search(r"_BIFVARINFO_DD_|^README|^DATA_POLICY", name):
                continue
            # Keep the source's timestamps, so the output is byte-identical
            # when the source is.
            member = zipfile.ZipInfo(name, date_time=info.date_time)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = info.external_attr
            out.writestr(member, raw)


def main() -> None:
    """Fetch the site archives, trim them, and save the site list."""
    for old in HERE.glob("*.zip"):
        old.unlink()
        sidecar_path(old).unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for site, (start, end) in SITES.items():
            (path,) = fetch(site, tmp)
            _trimmed(path, HERE / path.name, start, end)
            sidecar = sidecar_path(path)
            sidecar_path(HERE / path.name).write_bytes(sidecar.read_bytes())

    response = httpx.post(
        SPARQL_URL,
        data={"query": SITES_QUERY},
        headers={"Accept": "application/sparql-results+json"},
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()
    body["results"]["bindings"] = [
        b for b in body["results"]["bindings"] if b["siteId"]["value"] in SITES
    ]
    (HERE / "sites.json").write_text(json.dumps(body, indent=1) + "\n")


if __name__ == "__main__":
    main()
