"""Nodes that read FLUXNET data products, the archives ONEFlux v1.3 writes per site.

Every regional network publishes the same archive layout, so connectors for the
hubs that serve them build their standardisation graphs from these nodes and their
own. An archive holds, among other files:

- `<N>_<site>_FLUXNET_FLUXMET_<res>_<years>_<version>.csv`: the data, one file
  per resolution (`HH`, `DD`, `WW`, `MM`, `YY`);
- `<N>_<site>_FLUXNET_BIFVARINFO_<res>_...csv`: unit, definition and sensor
  height of every data column, in BADM Interchange Format (BIF);
- `<N>_<site>_FLUXNET_BIF_...csv`: site metadata in BIF, including the UTC offset
  of the data's clock;
- `DATA_POLICY_LICENSE_AND_INSTRUCTIONS.txt`: the licence.

Only daily (`DD`) files are read for now. Every node takes and returns a mapping
from archive path to that archive's part, so it acts on all archives at once.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
from hamilton.function_modifiers import tag

from .errors import ProviderError

FILL_VALUE = -9999.0

CF_UNITS = {
    "%": "%",
    "Decimal degrees": "degree",
    "W m-2": "W m-2",
    "adimensional": "1",
    "deg C": "degC",
    "gC m-2 d-1": "g m-2 d-1",
    "hPa": "hPa",
    "kPa": "kPa",
    "m s-1": "m s-1",
    "mm": "mm",
    "mm d-1": "mm d-1",
    "nondimensional": "1",
    "µmolCO2 m-2 s-1": "umol m-2 s-1",
    "µmolCO2 mol-1": "umol mol-1",
    "µmolPhoton m-2 s-1": "umol m-2 s-1",
}
"""CF equivalents of the unit strings FLUXNET writes.

Renaming only: each pair is the same unit, so values are unchanged. The species
in `µmolCO2` and `gC` is not part of the CF unit; it is in each variable's
definition.
"""

_PROFILE_INDEX = re.compile(r"^(?P<base>.+)_(?P<index>\d+)$")
_LICENCE = re.compile(r"shared under the (\S+) (?:data use )?license")


@dataclass(frozen=True)
class ArchiveText:
    """The text of the files in one archive that standardisation reads.

    Attributes:
        data: The daily data file.
        variable_info: `BIFVARINFO_DD`, describing each data column.
        site_info: The site BIF.
        policy: The data policy and licence.
    """

    data: str
    variable_info: str
    site_info: str
    policy: str


@dataclass(frozen=True)
class Variable:
    """One data column, as one `BIFVARINFO` entry describes it.

    Attributes:
        name: The column name, e.g. `"SWC_F_MDS_1"`.
        units: The unit string as the archive writes it, e.g. `"deg C"`.
        definition: The archive's description of the variable.
        height: Sensor height in metres, negative below ground, if given.
    """

    name: str
    units: str
    definition: str
    height: float | None


@dataclass(frozen=True)
class Site:
    """A site, as its archive's site BIF describes it.

    Attributes:
        site: The FLUXNET site code, e.g. `"UK-Cvn"`.
        site_name: The site's name, e.g. `"Coveney"`.
        lat: Latitude, in degrees north.
        lon: Longitude, in degrees east.
        elevation: Elevation above sea level, in metres, if given.
        utc_offset: Hours from UTC to the data's clock.
        igbp: The site's IGBP land-cover class, e.g. `"GRA"`.
        network: The network that prepared the data, e.g. `"EUF"`.
        processing_center: Where ONEFlux was run, e.g. `"EUDB_ICOS"`.
        oneflux_version: The full ONEFlux version, e.g. `"1.3.2-rc"`.
    """

    site: str
    site_name: str
    lat: float
    lon: float
    elevation: float | None
    utc_offset: float
    igbp: str
    network: str
    processing_center: str
    oneflux_version: str


@dataclass(frozen=True)
class Table:
    """The rows of one archive's daily data file.

    Attributes:
        dates: The local date of each row, as `datetime64[D]`.
        columns: Each data column, by name.
    """

    dates: np.ndarray
    columns: dict[str, np.ndarray]


def _decode(raw: bytes) -> str:
    # Some networks write Latin-1 (µ as 0xB5), others UTF-8.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _member(archive: zipfile.ZipFile, path: Path, pattern: str) -> str:
    names = [n for n in archive.namelist() if re.search(pattern, Path(n).name)]
    if len(names) != 1:
        found = "none" if not names else ", ".join(names)
        raise ProviderError(
            f"{path} should hold one file matching {pattern!r}; found {found}"
        )
    return names[0]


def _bif_groups(text: str) -> dict[str, list[dict[str, str]]]:
    """Group BIF rows into `{VARIABLE_GROUP: [{VARIABLE: DATAVALUE}, ...]}`.

    The `SITE_ID` column becomes a `SITE_ID` entry in every group.
    """
    groups: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(text)):
        group = groups[row["VARIABLE_GROUP"], row["GROUP_ID"]]
        group["SITE_ID"] = row["SITE_ID"]
        group.setdefault(row["VARIABLE"], row["DATAVALUE"])
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (name, _), values in groups.items():
        result[name].append(values)
    return result


def _one(groups: dict[str, list[dict[str, str]]], group: str, path: Path):
    entries = groups.get(group, [])
    if len(entries) != 1:
        raise ProviderError(
            f"{path}: expected one {group} entry in the site BIF, found {len(entries)}"
        )
    return entries[0]


def _float(value: str | None) -> float | None:
    return None if value in (None, "") else float(value)


def _read_archive(path: Path) -> ArchiveText:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ProviderError(f"{path} is not a ZIP archive") from None
    with archive:

        def read(pattern: str) -> str:
            return _decode(archive.read(_member(archive, path, pattern)))

        return ArchiveText(
            data=read(r"_FLUXMET_DD_.*\.csv$"),
            variable_info=read(r"_BIFVARINFO_DD_.*\.csv$"),
            site_info=read(r"_FLUXNET_BIF_.*\.csv$"),
            policy=read(r"^DATA_POLICY.*\.txt$"),
        )


@tag(action="reads")
def archive_texts(archive_paths: list[Path]) -> dict[Path, ArchiveText]:
    """Read the four files standardisation needs from each archive, as text.

    The archives are read in place, without extracting them. Text is decoded as
    UTF-8, or as Latin-1 where that fails, since networks differ.

    Raises:
        ProviderError: If a path is not a ZIP archive, or an archive does not
            hold exactly one of each file.
    """
    return {path: _read_archive(path) for path in archive_paths}


@tag(action="reads")
def sites(archive_texts: dict[Path, ArchiveText]) -> dict[Path, Site]:
    """Read each archive's site metadata from its site BIF.

    Raises:
        ProviderError: If the BIF does not have exactly one header, location,
            UTC offset, land-cover class and ONEFlux product entry, or lacks a
            latitude, longitude or UTC offset.
    """
    result = {}
    for path, text in archive_texts.items():
        groups = _bif_groups(text.site_info)
        header = _one(groups, "GRP_HEADER", path)
        location = _one(groups, "GRP_LOCATION", path)
        oneflux = _one(groups, "GRP_ONEFLUX", path)
        lat = _float(location.get("LOCATION_LAT"))
        lon = _float(location.get("LOCATION_LONG"))
        offset = _float(_one(groups, "GRP_UTC_OFFSET", path).get("UTC_OFFSET"))
        if lat is None or lon is None or offset is None:
            raise ProviderError(f"{path}: the site BIF lacks a location or UTC offset")
        result[path] = Site(
            site=header["SITE_ID"],
            site_name=header.get("SITE_NAME", ""),
            lat=lat,
            lon=lon,
            elevation=_float(location.get("LOCATION_ELEV")),
            utc_offset=offset,
            igbp=_one(groups, "GRP_IGBP", path).get("IGBP", ""),
            network=oneflux.get("PRODUCT_SOURCE_NETWORK", ""),
            processing_center=oneflux.get("PRODUCT_PROCESSING_CENTER", ""),
            oneflux_version=oneflux.get("PRODUCT_ONEFLUX_VERSION", ""),
        )
    return result


@tag(action="reads")
def licences(archive_texts: dict[Path, ArchiveText]) -> dict[Path, str]:
    """Read the licence each archive's data policy states, e.g. `"CC-BY-4.0"`.

    Raises:
        ProviderError: If the policy does not name a licence.
    """
    result = {}
    for path, text in archive_texts.items():
        match = _LICENCE.search(text.policy)
        if match is None:
            raise ProviderError(f"{path}: cannot find the licence in the data policy")
        result[path] = match[1]
    return result


@tag(action="reads")
def variable_entries(
    archive_texts: dict[Path, ArchiveText],
) -> dict[Path, dict[str, list[Variable]]]:
    """Read every `BIFVARINFO` entry, grouped by the column it describes.

    A column can have several entries, one per period of its sensor metadata,
    e.g. after an instrument was replaced; they are kept in the archive's order.
    """
    result = {}
    for path, text in archive_texts.items():
        entries: dict[str, list[Variable]] = defaultdict(list)
        for entry in _bif_groups(text.variable_info).get("GRP_VAR_INFO", []):
            name = entry["VAR_INFO_VARNAME"]
            entries[name].append(
                Variable(
                    name=name,
                    units=entry.get("VAR_INFO_UNIT", ""),
                    definition=entry.get("VAR_INFO_DEFINITION", ""),
                    height=_float(entry.get("VAR_INFO_HEIGHT")),
                )
            )
        result[path] = dict(entries)
    return result


@tag(action="interprets")
def variables(
    variable_entries: dict[Path, dict[str, list[Variable]]],
) -> dict[Path, dict[str, Variable]]:
    """Describe each column by its first `BIFVARINFO` entry.

    A judgement: later entries, which record a change of sensor metadata during
    the record, are dropped. They are allowed only if they keep the unit and,
    for a soil profile (`SWC_` or `TS_`), the sensor's height; other changes,
    such as a new instrument model, pass without note.

    Raises:
        ProviderError: If a later entry changes a column's unit, or a soil
            sensor's height.
    """
    result = {}
    for path, entries in variable_entries.items():
        kept = {}
        for name, versions in entries.items():
            first = versions[0]
            for later in versions[1:]:
                if later.units != first.units or (
                    name.startswith(("SWC_", "TS_")) and later.height != first.height
                ):
                    raise ProviderError(
                        f"{path}: {name} changes unit or depth within the record, "
                        "which xharvest cannot yet represent"
                    )
            kept[name] = first
        result[path] = kept
    return result


@tag(action="reads")
def raw_tables(archive_texts: dict[Path, ArchiveText]) -> dict[Path, Table]:
    """Read each daily data file: the local date of each row, and every column.

    Raises:
        ProviderError: If the file's first column is not `TIMESTAMP`.
    """
    result = {}
    for path, text in archive_texts.items():
        reader = csv.reader(io.StringIO(text.data))
        header = next(reader)
        if header[0] != "TIMESTAMP":
            raise ProviderError(f"{path}: the daily file does not start with TIMESTAMP")
        rows = list(reader)
        dates = np.array(
            [f"{r[0][:4]}-{r[0][4:6]}-{r[0][6:8]}" for r in rows],
            dtype="datetime64[D]",
        )
        values = np.array([row[1:] for row in rows], dtype=float).reshape(
            len(rows), len(header) - 1
        )
        columns = {name: values[:, i] for i, name in enumerate(header[1:])}
        result[path] = Table(dates=dates, columns=columns)
    return result


@tag(action="decodes")
def tables(raw_tables: dict[Path, Table]) -> dict[Path, Table]:
    """Replace FLUXNET's fill value, `-9999`, with NaN in every column."""
    result = {}
    for path, table in raw_tables.items():
        columns = {
            name: np.where(values == FILL_VALUE, np.nan, values)
            for name, values in table.columns.items()
        }
        result[path] = Table(dates=table.dates, columns=columns)
    return result


@tag(action="checks")
def described_tables(
    tables: dict[Path, Table], variables: dict[Path, dict[str, Variable]]
) -> dict[Path, Table]:
    """Check that `BIFVARINFO` describes every data column.

    Raises:
        ProviderError: If a column has no entry, since its unit is then unknown.
    """
    for path, table in tables.items():
        undescribed = [name for name in table.columns if name not in variables[path]]
        if undescribed:
            raise ProviderError(
                f"{path}: no BIFVARINFO entry for {', '.join(undescribed)}"
            )
    return tables


@tag(action="decodes")
def times(
    described_tables: dict[Path, Table], sites: dict[Path, Site]
) -> dict[Path, np.ndarray]:
    """Convert each row's local date to the UTC start of that day.

    The data keep local standard time, UTC plus the site's `UTC_OFFSET`, so a
    day starts at midnight minus the offset, in UTC. The archive README says
    local solar time; `SW_IN_POT` shows otherwise (see the provider page).
    """
    result = {}
    for path, table in described_tables.items():
        offset = np.timedelta64(timedelta(hours=sites[path].utc_offset))
        local = table.dates.astype("datetime64[ns]")
        result[path] = (local - offset).astype("datetime64[ns]")
    return result


@tag(action="reads")
def soil_profiles(
    described_tables: dict[Path, Table],
    variables: dict[Path, dict[str, Variable]],
    profiled_variables: tuple[str, ...],
) -> dict[Path, dict[str, dict[float, str]]]:
    """Map each soil sensor's depth to its column, for each profiled variable.

    FLUXNET numbers soil sensors (`SWC_F_MDS_1`, `SWC_F_MDS_2`, ...), but the
    numbers are not depths: they skip values and differ between variables and
    sites. A sensor's depth is the negative of its `VAR_INFO_HEIGHT`, in metres,
    rounded to 0.1 mm.

    Returns:
        `{path: {variable: {depth: column}}}`, depths ascending.

    Raises:
        ProviderError: If a sensor has no height, or two sensors of one
            variable share a depth.
    """
    result = {}
    for path, table in described_tables.items():
        profiles = {}
        for base in profiled_variables:
            depths: dict[float, str] = {}
            for name in table.columns:
                match = _PROFILE_INDEX.match(name)
                if not match or match["base"] != base:
                    continue
                height = variables[path][name].height
                if height is None:
                    raise ProviderError(
                        f"{path}: {name} has no VAR_INFO_HEIGHT, so its depth is "
                        "unknown"
                    )
                depth = round(-height, 4)
                if depth in depths:
                    raise ProviderError(
                        f"{path}: {depths[depth]} and {name} are both at "
                        f"{depth} m depth"
                    )
                depths[depth] = name
            profiles[base] = dict(sorted(depths.items()))
        result[path] = profiles
    return result


@tag(action="annotates")
def cf_units(
    kept_variables: dict[Path, dict[str, Variable]],
) -> dict[Path, dict[str, str]]:
    """Rename each kept column's unit string to its CF equivalent.

    Renaming only, from `CF_UNITS`: `deg C` becomes `degC`, `gC m-2 d-1` becomes
    `g m-2 d-1`. The values are unchanged.

    Raises:
        ProviderError: If a unit string has no known CF equivalent.
    """
    result = {}
    for path, kept in kept_variables.items():
        units = {}
        for name, variable in kept.items():
            if variable.units not in CF_UNITS:
                raise ProviderError(
                    f"FLUXNET variable {name} has unit {variable.units!r}, which "
                    "xharvest does not know a CF equivalent for"
                )
            units[name] = CF_UNITS[variable.units]
        result[path] = units
    return result
