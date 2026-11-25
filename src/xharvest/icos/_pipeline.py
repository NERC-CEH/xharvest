"""Nodes that standardise the ancillary measurements in ICOS ETC L2 archives.

`standardise` builds its graph from these and computes `datasets`, one Dataset per
BIF group in `GROUPS`, from `paths`. Every node acts on all the archives and
groups at once; most take and return a mapping from archive path to that
archive's part. BIF is read with `xharvest.fluxnet._bif` (ADR 3).

Each measurement stays one record, as the archive gives it: nothing is averaged,
pivoted into series, or classified, so the qualifiers that tell records apart
(type, statistic, method, species, organ, approach, depth) are kept beside the
values for the user to select on.
"""

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xarray as xr
from hamilton.function_modifiers import tag

from .. import __version__
from ..errors import ProviderError
from ..fluxnet import _bif
from ..fluxnet._fetch import DATA_URL
from ..provenance import Retrieval, history_line, is_sidecar, read_sidecar, utc_now

GROUPS = {
    "LAI": ("LAI",),
    "BIOMASS": ("BIOMASS",),
    "HEIGHTC": ("HEIGHTC", "HEIGHTC_U"),
    "SOIL_TEX": (
        "SOIL_TEX_SAND",
        "SOIL_TEX_SILT",
        "SOIL_TEX_CLAY",
        "SOIL_TEX_ROCK",
        "SOIL_TEX_FIELD_CAP",
        "SOIL_TEX_WILT",
        "SOIL_TEX_SAT",
        "SOIL_TEX_WATER_HOLD_CAP",
    ),
    "SOIL_STOCK": (
        "SOIL_STOCK_C_ORG",
        "SOIL_STOCK_N_TOT",
        "SOIL_STOCK_P",
        "SOIL_STOCK_K",
    ),
}
"""The BIF groups `standardise` keeps, without their `GRP_` prefix, and the
variables in each that hold measured values. Every other variable of a kept
group is a qualifier, kept as a coordinate."""

CF_UNITS = {
    "m2 m-2": "m2 m-2",
    "m": "m",
    "%": "%",
    "%vol": "%",
    "g C m-2": "g m-2",
    "g N m-2": "g m-2",
    "g P m-2": "g m-2",
    "g K m-2": "g m-2",
    "kgDM m-2": "kg m-2",
    "cm": "cm",
    "days": "d",
}
"""CF equivalents of the unit strings the variable dictionary uses.

Renaming only: each pair is the same unit, so values are unchanged. What is
weighed (carbon, nitrogen, dry matter) and what a percentage is of (mass, or
volume for `%vol`) is not part of the CF unit; it is in each variable's
description, and the original string is kept as `provider_units`.
"""

NUMERIC_QUALIFIER_UNITS = {"cm", "days", "integer number", "decimal number"}
"""Dictionary units of qualifiers kept as numbers rather than strings."""

DRY_MATTER = "kgDM m-2"

TITLE = "ICOS ecosystem station ancillary data: {}"

_DATE = re.compile(r"_DATE(_START|_END)?$")


@dataclass(frozen=True)
class ArchiveText:
    """The text of the files in one archive that standardisation reads.

    Attributes:
        ancillary: The station's ancillary measurements, in BIF.
        site_info: The station's site metadata, in BIF.
        dictionary: `BIF_Ancillary_Variables.csv`: the description and unit of
            every ancillary variable.
    """

    ancillary: str
    site_info: str
    dictionary: str


@dataclass(frozen=True)
class Site:
    """A station, as its archive's site metadata describes it.

    Attributes:
        site: The station code, e.g. `"UK-AMo"`.
        site_name: The station's name, e.g. `"Auchencorth Moss"`.
        lat: Latitude, in degrees north.
        lon: Longitude, in degrees east.
    """

    site: str
    site_name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Entry:
    """One variable in the dictionary.

    Attributes:
        description: What the variable is.
        unit: Its unit, or for a qualifier what kind of value it takes, e.g.
            `"free text"` or `"LIST(STATISTIC)"`.
    """

    description: str
    unit: str


def _read_archive(path: Path) -> ArchiveText:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ProviderError(f"{path} is not a ZIP archive") from None
    with archive:

        def read(pattern: str) -> str:
            return _bif.decode(archive.read(_bif.member(archive, path, pattern)))

        return ArchiveText(
            ancillary=read(r"_ANCILLARY_(INTERIM_)?L2\.csv$"),
            site_info=read(r"_SITEINFO_(INTERIM_)?L2\.csv$"),
            dictionary=read(r"^BIF_Ancillary_Variables\.csv$"),
        )


def _number(value: str) -> float:
    # A decimal comma is read as a decimal point; see `values`.
    if value.count(",") == 1 and "." not in value:
        value = value.replace(",", ".")
    return float(value)


_NAT = np.datetime64("NaT", "ns")

_PRECISION = {
    4: np.timedelta64(1, "Y"),
    6: np.timedelta64(1, "M"),
    8: np.timedelta64(1, "D"),
    10: np.timedelta64(1, "h"),
    12: None,
    14: None,
}
"""The period a BIF date of each length names, from its start; None for an instant."""


def _period(value: str) -> tuple[np.datetime64, np.datetime64]:
    """The start and end of the period a BIF date string names."""
    if not value.isdigit() or len(value) not in _PRECISION:
        return _NAT, _NAT
    # ISO 8601 to the string's precision, which numpy keeps as the unit.
    text = value[:4]
    for i, sep in [(4, "-"), (6, "-"), (8, "T"), (10, ":"), (12, ":")]:
        if len(value) > i:
            text += sep + value[i : i + 2]
    start = np.datetime64(text)
    step = _PRECISION[len(value)]
    end = start if step is None else start + step
    return start.astype("datetime64[ns]"), end.astype("datetime64[ns]")


@tag(action="selects")
def archive_paths(paths: list[Path]) -> list[Path]:
    """Keep the archives among `paths`, sorted, and drop provenance sidecars.

    So a glob over the download directory works.

    Raises:
        ValueError: If no archives remain.
    """
    archives = sorted(p for p in paths if not is_sidecar(p))
    if not archives:
        raise ValueError("no ETC L2 archives to standardise")
    return archives


@tag(action="reads")
def retrievals(archive_paths: list[Path]) -> dict[Path, Retrieval]:
    """Read each archive's provenance sidecar, written by `fetch`.

    The sidecar records where and when the archive was downloaded, and the
    citation and licence the portal gives for it, none of which the archive
    itself holds.

    Raises:
        FileNotFoundError: If an archive has no sidecar.
    """
    return {path: read_sidecar(path) for path in archive_paths}


@tag(action="reads")
def archive_texts(archive_paths: list[Path]) -> dict[Path, ArchiveText]:
    """Read the ancillary file, site metadata and variable dictionary, as text.

    The archives are read in place, without extracting them.

    Raises:
        ProviderError: If a path is not a ZIP archive, or an archive does not
            hold exactly one of each file. About one station in ten has no
            ancillary file.
    """
    return {path: _read_archive(path) for path in archive_paths}


@tag(action="reads")
def sites(archive_texts: dict[Path, ArchiveText]) -> dict[Path, Site]:
    """Read each station's code, name and location from its site metadata.

    Raises:
        ProviderError: If the metadata lacks a header or a location.
    """
    result = {}
    for path, text in archive_texts.items():
        groups = _bif.entries(text.site_info)
        header = _bif.one(groups, "GRP_HEADER", path)
        location = _bif.one(groups, "GRP_LOCATION", path)
        lat = _bif.number(location.get("LOCATION_LAT"))
        lon = _bif.number(location.get("LOCATION_LONG"))
        if lat is None or lon is None:
            raise ProviderError(f"{path}: the site metadata lacks a location")
        result[path] = Site(
            site=header["SITE_ID"],
            site_name=header.get("SITE_NAME", ""),
            lat=lat,
            lon=lon,
        )
    return result


@tag(action="reads")
def dictionaries(
    archive_texts: dict[Path, ArchiveText],
) -> dict[Path, dict[str, Entry]]:
    """Read each archive's variable dictionary: description and unit by name."""
    result = {}
    for path, text in archive_texts.items():
        rows = csv.DictReader(io.StringIO(text.dictionary))
        result[path] = {
            row["VARIABLE NAME"].strip(): Entry(
                description=row["VARIABLE DESCRIPTION"].strip(),
                unit=row["UNIT"].strip(),
            )
            for row in rows
        }
    return result


@tag(action="reads")
def entries(
    archive_texts: dict[Path, ArchiveText],
) -> dict[Path, dict[str, list[dict[str, str]]]]:
    """Read every ancillary entry, grouped by its BIF group, e.g. `GRP_LAI`.

    An entry is the rows sharing a `GROUP_ID`: one measurement and its
    qualifiers.
    """
    return {path: _bif.entries(text.ancillary) for path, text in archive_texts.items()}


@tag(action="selects")
def kept_entries(
    entries: dict[Path, dict[str, list[dict[str, str]]]],
) -> dict[Path, dict[str, list[dict[str, str]]]]:
    """Keep the groups in `GROUPS`, and in each the entries holding a value.

    An entry none of whose value variables is set describes a sample without
    reporting a measurement of it, so it is dropped. Every other group, such as
    soil chemistry, litter or tree counts, is dropped.

    Returns:
        `{path: {group: [entry, ...]}}`, with every group in `GROUPS`, empty
        where the station has no entry.
    """
    result = {}
    for path, groups in entries.items():
        kept = {}
        for group, value_names in GROUPS.items():
            kept[group] = [
                entry
                for entry in groups.get(f"GRP_{group}", [])
                if any(entry.get(name, "") != "" for name in value_names)
            ]
        result[path] = kept
    return result


@tag(action="selects")
def dry_matter_entries(
    kept_entries: dict[Path, dict[str, list[dict[str, str]]]],
) -> dict[Path, dict[str, list[dict[str, str]]]]:
    """Keep only the biomass entries in dry matter, `kgDM m-2`.

    `BIOMASS_UNIT` varies by entry, and a few are in carbon, `gC m-2`, which
    weighs something else, so cannot share a variable with dry matter. Those
    are dropped for now.

    Raises:
        ProviderError: If a biomass entry has neither unit.
    """
    result = {}
    for path, groups in kept_entries.items():
        biomass = []
        for entry in groups["BIOMASS"]:
            unit = entry.get("BIOMASS_UNIT", "")
            if unit == DRY_MATTER:
                biomass.append(entry)
            elif unit != "gC m-2":
                raise ProviderError(
                    f"{path}: a biomass entry has unit {unit!r}, which xharvest "
                    "does not know"
                )
        result[path] = {**groups, "BIOMASS": biomass}
    return result


@tag(action="checks")
def checked_dictionaries(
    dictionaries: dict[Path, dict[str, Entry]],
) -> dict[Path, dict[str, Entry]]:
    """Check that every value variable is in each dictionary, with a known unit.

    The unit of each value comes from the dictionary, and is renamed to CF from
    `CF_UNITS`; biomass has its own per-entry unit, checked by
    `dry_matter_entries`.

    Raises:
        ProviderError: If a value variable is missing from a dictionary, or its
            unit has no known CF equivalent.
    """
    for path, dictionary in dictionaries.items():
        for group, names in GROUPS.items():
            for name in names:
                if group == "BIOMASS":
                    continue
                entry = dictionary.get(name)
                if entry is None:
                    raise ProviderError(f"{path}: the dictionary lacks {name}")
                if entry.unit not in CF_UNITS:
                    raise ProviderError(
                        f"{path}: {name} has unit {entry.unit!r}, which xharvest "
                        "does not know a CF equivalent for"
                    )
    return dictionaries


@tag(action="interprets")
def values(
    dry_matter_entries: dict[Path, dict[str, list[dict[str, str]]]],
) -> dict[Path, dict[str, dict[str, np.ndarray]]]:
    """Read each value variable as a number, one per entry; NaN where unset.

    A judgement: a value with one comma and no point, such as `7,9`, is read as
    a decimal comma, `7.9`. One biomass value is written so, among about 17,000.

    Returns:
        `{path: {group: {variable: values}}}`.

    Raises:
        ProviderError: If a value is not a number.
    """
    result = {}
    for path, groups in dry_matter_entries.items():
        by_group = {}
        for group, group_entries in groups.items():
            columns = {}
            for name in GROUPS[group]:
                column = np.full(len(group_entries), np.nan)
                for i, entry in enumerate(group_entries):
                    raw = entry.get(name, "")
                    if raw == "":
                        continue
                    try:
                        column[i] = _number(raw)
                    except ValueError:
                        raise ProviderError(
                            f"{path}: {name} has the value {raw!r}, which is not "
                            "a number"
                        ) from None
                columns[name] = column
            by_group[group] = columns
        result[path] = by_group
    return result


@tag(action="interprets")
def periods(
    dry_matter_entries: dict[Path, dict[str, list[dict[str, str]]]],
) -> dict[Path, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    """Give each entry a time, and the period it covers, from its date strings.

    A judgement: a BIF date is as precise as it is long, so `2023` names that
    year, `202306` that month, `20230615` that day, and `202306151200` an
    instant. An entry's period runs from the start of `<group>_DATE_START` to
    the end of `<group>_DATE_END` where it gives both, and otherwise is the
    period `<group>_DATE` names. Its time is the start of `<group>_DATE` if
    given, else of its period. A date that is missing or not digits is NaT.

    Dates are the station's local dates, as the archive writes them: they are
    not converted to UTC.

    Returns:
        `{path: {group: (time, start, end)}}`.
    """
    result = {}
    for path, groups in dry_matter_entries.items():
        by_group = {}
        for group, group_entries in groups.items():
            n = len(group_entries)
            time = np.full(n, np.datetime64("NaT", "ns"))
            start = np.full(n, np.datetime64("NaT", "ns"))
            end = np.full(n, np.datetime64("NaT", "ns"))
            for i, entry in enumerate(group_entries):
                date = _period(entry.get(f"{group}_DATE", ""))
                first = _period(entry.get(f"{group}_DATE_START", ""))
                last = _period(entry.get(f"{group}_DATE_END", ""))
                if not (np.isnat(first[0]) or np.isnat(last[1])):
                    start[i], end[i] = first[0], last[1]
                else:
                    start[i], end[i] = date
                time[i] = date[0] if not np.isnat(date[0]) else start[i]
            by_group[group] = (time, start, end)
        result[path] = by_group
    return result


@tag(action="reshapes")
def qualifiers(
    dry_matter_entries: dict[Path, dict[str, list[dict[str, str]]]],
    checked_dictionaries: dict[Path, dict[str, Entry]],
) -> dict[Path, dict[str, dict[str, np.ndarray]]]:
    """Collect every other variable of each entry, as a column per variable.

    Every variable an entry gives besides its values, dates and biomass unit
    becomes a qualifier column, so nothing the archive says about a
    measurement is lost. A qualifier whose dictionary unit is numeric (`cm`,
    `days`, `integer number` or `decimal number`), such as a depth or a count,
    is a float, NaN where unset; every other is a string, empty where unset.

    Returns:
        `{path: {group: {qualifier: column}}}`.

    Raises:
        ProviderError: If a numeric qualifier is not a number.
    """
    result = {}
    for path, groups in dry_matter_entries.items():
        dictionary = checked_dictionaries[path]
        by_group = {}
        for group, group_entries in groups.items():
            skipped = {*GROUPS[group], "SITE_ID", "BIOMASS_UNIT"}
            names = sorted(
                {
                    name
                    for entry in group_entries
                    for name in entry
                    if name not in skipped and not _DATE.search(name)
                }
            )
            columns = {}
            for name in names:
                raw = [entry.get(name, "") for entry in group_entries]
                entry = dictionary.get(name)
                if entry is not None and entry.unit in NUMERIC_QUALIFIER_UNITS:
                    try:
                        columns[name] = np.array(
                            [np.nan if r == "" else _number(r) for r in raw]
                        )
                    except ValueError:
                        raise ProviderError(
                            f"{path}: {name} has a value that is not a number"
                        ) from None
                else:
                    columns[name] = np.array(raw, dtype=str)
            by_group[group] = columns
        result[path] = by_group
    return result


@tag(action="reshapes")
def records(
    values: dict[Path, dict[str, dict[str, np.ndarray]]],
    periods: dict[Path, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]],
    qualifiers: dict[Path, dict[str, dict[str, np.ndarray]]],
    sites: dict[Path, Site],
) -> dict[str, xr.Dataset]:
    """Arrange each group's entries, from every archive, along one `record` dim.

    Each entry is one record. Its values are data variables; its station,
    location, time, period and qualifiers are coordinates on `record`. A
    qualifier one station gives and another does not is empty, or NaN, at the
    other's records.
    """
    result = {}
    for group, names in GROUPS.items():
        numeric: dict[str, bool] = {}
        for by_group in qualifiers.values():
            for name, column in by_group[group].items():
                numeric[name] = numeric.get(name, False) or column.dtype.kind == "f"
        pieces = []
        for path, site in sites.items():
            time, start, end = periods[path][group]
            n = len(time)
            coords = {
                "site": ("record", np.full(n, site.site, dtype=object)),
                "site_name": ("record", np.full(n, site.site_name, dtype=object)),
                "lat": ("record", np.full(n, site.lat)),
                "lon": ("record", np.full(n, site.lon)),
                "time": ("record", time),
                "time_bounds": (("record", "nv"), np.stack([start, end], axis=-1)),
            }
            given = qualifiers[path][group]
            for name in sorted(numeric):
                if name in given:
                    column = given[name]
                elif numeric[name]:
                    column = np.full(n, np.nan)
                else:
                    column = np.full(n, "")
                kind = float if numeric[name] else object
                coords[name] = ("record", column.astype(kind))
            data_vars = {name: ("record", values[path][group][name]) for name in names}
            pieces.append(xr.Dataset(data_vars, coords=coords))
        ds = xr.concat(pieces, dim="record", data_vars="all", coords="all")
        for name, coord in ds.coords.items():
            if coord.dtype == object:
                ds.coords[name] = coord.astype(str)
        result[group] = ds
    return result


@tag(action="annotates")
def variable_attributes(
    checked_dictionaries: dict[Path, dict[str, Entry]],
) -> dict[str, dict[str, str]]:
    """Collect each value variable's CF `units`, provider unit and description.

    Taken from the first archive's dictionary, in path order; the dictionary is
    the same file in every archive. Biomass is in dry matter, as
    `dry_matter_entries` keeps it.
    """
    dictionary = next(iter(checked_dictionaries.values()))
    result = {}
    for group, names in GROUPS.items():
        for name in names:
            if group == "BIOMASS":
                description = dictionary.get(name, Entry("Biomass", "")).description
                result[name] = {
                    "units": CF_UNITS[DRY_MATTER],
                    "provider_units": DRY_MATTER,
                    "description": f"{description}, as dry matter",
                }
                continue
            entry = dictionary[name]
            result[name] = {
                "units": CF_UNITS[entry.unit],
                "provider_units": entry.unit,
                "description": entry.description,
            }
    return result


@tag(action="annotates")
def coordinate_attributes(
    checked_dictionaries: dict[Path, dict[str, Entry]],
) -> dict[str, dict[str, str]]:
    """Describe each qualifier from the dictionary, with a CF unit where it has one.

    A qualifier the dictionary does not list gets no attributes.
    """
    dictionary = next(iter(checked_dictionaries.values()))
    result = {}
    for name, entry in dictionary.items():
        attrs = {"description": entry.description}
        if entry.unit in CF_UNITS:
            attrs.update(units=CF_UNITS[entry.unit], provider_units=entry.unit)
        result[name] = attrs
    return result


@tag(action="annotates")
def global_attributes(retrievals: dict[Path, Retrieval]) -> dict[str, str]:
    """Collect the provenance attributes, and every station's citation.

    `history` has a line per download, from the sidecars, and one for this
    standardisation; `references` has each archive's citation, and `license`
    each licence, as the portal gives them.
    """
    history = sorted(history_line(r) for r in retrievals.values())
    history.append(f"{utc_now()} standardised (xharvest {__version__})")
    citations = sorted({r.metadata.get("citation", "") for r in retrievals.values()})
    licences = sorted({r.metadata.get("licence", "") for r in retrievals.values()})
    return {
        "institution": "ICOS Ecosystem Thematic Centre (ETC)",
        "source": f"ICOS ETC L2 archive, ICOS Carbon Portal, {DATA_URL}",
        "license": "; ".join(lic for lic in licences if lic),
        "references": "\n".join(c for c in citations if c),
        "history": "\n".join(history),
    }


@tag(action="annotates")
def datasets(
    records: dict[str, xr.Dataset],
    variable_attributes: dict[str, dict[str, str]],
    coordinate_attributes: dict[str, dict[str, str]],
    global_attributes: dict[str, str],
) -> dict[str, xr.Dataset]:
    """Set the attributes of each group's Dataset.

    `time` carries `bounds = "time_bounds"`, and `time` and its bounds share one
    encoding, as CF requires.
    """
    result = {}
    for group, ds in records.items():
        ds = ds.copy()
        for name in ds.data_vars:
            ds[name].attrs = dict(variable_attributes[str(name)])
        for name in ds.coords:
            if name in coordinate_attributes:
                ds[name].attrs = dict(coordinate_attributes[str(name)])
        ds.site.attrs.update(long_name="ICOS station code")
        ds.site_name.attrs.update(long_name="station name")
        ds.lat.attrs.update(standard_name="latitude", units="degrees_north")
        ds.lon.attrs.update(standard_name="longitude", units="degrees_east")
        ds.time.attrs.update(
            standard_name="time",
            long_name="local date of the measurement, as the archive gives it, "
            "not converted to UTC",
            bounds="time_bounds",
        )
        ds.time.encoding["units"] = "minutes since 1970-01-01 00:00:00"
        ds.attrs = {"title": TITLE.format(group), **global_attributes}
        result[group] = ds
    return result
