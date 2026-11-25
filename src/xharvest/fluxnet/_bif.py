"""Read BADM Interchange Format (BIF), FLUXNET's format for site metadata.

BIF is a long CSV table, `SITE_ID, GROUP_ID, VARIABLE_GROUP, VARIABLE, DATAVALUE`,
in which the rows sharing a `GROUP_ID` make one entry of a group: one location,
one sensor's description, one LAI measurement. FLUXNET archives use it for site
metadata and variable descriptions, and ICOS ETC archives for ancillary
measurements, so `xharvest.fluxnet._archive` and `xharvest.icos` both read it
from here (ADR 3).

These are plain functions, not graph nodes: the graphs call them inside nodes.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from ..errors import ProviderError


def decode(raw: bytes) -> str:
    """Decode a file's bytes as UTF-8, or as Latin-1 where that fails.

    Some networks write Latin-1 (µ as 0xB5), others UTF-8.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def member(archive: zipfile.ZipFile, path: Path, pattern: str) -> str:
    """The name of the one member of `archive` whose file name matches `pattern`.

    Raises:
        ProviderError: If no member, or more than one, matches.
    """
    names = [n for n in archive.namelist() if re.search(pattern, Path(n).name)]
    if len(names) != 1:
        found = "none" if not names else ", ".join(names)
        raise ProviderError(
            f"{path} should hold one file matching {pattern!r}; found {found}"
        )
    return names[0]


def entries(text: str) -> dict[str, list[dict[str, str]]]:
    """Group BIF rows into `{VARIABLE_GROUP: [{VARIABLE: DATAVALUE}, ...]}`.

    Each entry is one `GROUP_ID`, in the order the file first gives it. The
    `SITE_ID` column becomes a `SITE_ID` item in every entry. Where an entry
    repeats a variable, the first value is kept.
    """
    groups: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(text)):
        entry = groups[row["VARIABLE_GROUP"], row["GROUP_ID"]]
        entry["SITE_ID"] = row["SITE_ID"]
        entry.setdefault(row["VARIABLE"], row["DATAVALUE"])
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (name, _), values in groups.items():
        result[name].append(values)
    return dict(result)


def one(
    groups: dict[str, list[dict[str, str]]], group: str, path: Path
) -> dict[str, str]:
    """The single entry of `group`.

    Raises:
        ProviderError: If the group has no entry, or more than one.
    """
    found = groups.get(group, [])
    if len(found) != 1:
        raise ProviderError(
            f"{path}: expected one {group} entry in the site BIF, found {len(found)}"
        )
    return found[0]


def number(value: str | None) -> float | None:
    """A BIF value as a float, or None if it is missing or empty."""
    return None if value in (None, "") else float(value)
