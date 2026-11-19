"""Read FLUXNET data products, the ZIP archives ONEFlux v1.3 writes for each site.

Every regional network publishes the same archive layout, so connectors for the
hubs that serve them share this reader. An archive holds, among other files:

- `<N>_<site>_FLUXNET_FLUXMET_<res>_<years>_<version>.csv`: the data, one file
  per resolution (`HH`, `DD`, `WW`, `MM`, `YY`);
- `<N>_<site>_FLUXNET_BIFVARINFO_<res>_...csv`: unit, definition and sensor
  height of every data column, in BADM Interchange Format (BIF);
- `<N>_<site>_FLUXNET_BIF_...csv`: site metadata in BIF, including the UTC offset
  of the data's clock;
- `DATA_POLICY_LICENSE_AND_INSTRUCTIONS.txt`: the licence.

Only daily (`DD`) files are read for now. Timestamps are local standard time,
`UTC + UTC_OFFSET`; a daily value covers the local day.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from os import PathLike
from pathlib import Path

import numpy as np

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

_PROFILE_INDEX = re.compile(r"^(?P<base>.+)_(?P<index>\d+)(?P<qc>_QC)?$")


@dataclass(frozen=True)
class Variable:
    """One data column, as `BIFVARINFO` describes it.

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

    @property
    def cf_units(self) -> str:
        """The CF equivalent of `units`.

        Raises:
            ProviderError: If the unit string is not in `CF_UNITS`.
        """
        try:
            return CF_UNITS[self.units]
        except KeyError:
            raise ProviderError(
                f"FLUXNET variable {self.name} has unit {self.units!r}, which "
                "xharvest does not know a CF equivalent for"
            ) from None


@dataclass(frozen=True)
class Archive:
    """The daily data of one site's FLUXNET archive.

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
        licence: The licence the archive states, e.g. `"CC-BY-4.0"`.
        dates: The local date of each row, as `datetime64[D]`.
        columns: Each data column, with fill values as NaN.
        variables: Each data column's `BIFVARINFO` entry.
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
    licence: str
    dates: np.ndarray
    columns: dict[str, np.ndarray]
    variables: dict[str, Variable]

    @property
    def time(self) -> np.ndarray:
        """The UTC start of each row's local day, as `datetime64[ns]`."""
        offset = np.timedelta64(timedelta(hours=self.utc_offset))
        return (self.dates.astype("datetime64[ns]") - offset).astype("datetime64[ns]")

    def profile(self, base: str) -> dict[float, str]:
        """Map each depth of a soil profile to the column measured there.

        Args:
            base: The variable without its index, e.g. `"SWC_F_MDS"`.

        Returns:
            Depth in metres below ground, positive down, to the column name,
            ordered by depth. Profile indices are not depths: they skip numbers
            and differ between variables and sites, so `VAR_INFO_HEIGHT` is used.

        Raises:
            ProviderError: If a column has no height, or two share a depth.
        """
        depths: dict[float, str] = {}
        for name in self.columns:
            match = _PROFILE_INDEX.match(name)
            if not match or match["base"] != base or match["qc"]:
                continue
            height = self.variables[name].height
            if height is None:
                raise ProviderError(
                    f"{self.site}: {name} has no VAR_INFO_HEIGHT, so its depth "
                    "is unknown"
                )
            depth = round(-height, 4)
            if depth in depths:
                raise ProviderError(
                    f"{self.site}: {depths[depth]} and {name} are both at "
                    f"{depth} m depth"
                )
            depths[depth] = name
        return dict(sorted(depths.items()))


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


def _read_bif(text: str) -> dict[str, list[dict[str, str]]]:
    """Group BIF rows into `{VARIABLE_GROUP: [{VARIABLE: DATAVALUE}, ...]}`.

    The `SITE_ID` column becomes a `SITE_ID` entry in every group.
    """
    groups: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in csv.DictReader(io.StringIO(text)):
        groups[row["VARIABLE_GROUP"], row["GROUP_ID"]]["SITE_ID"] = row["SITE_ID"]
        group = groups[row["VARIABLE_GROUP"], row["GROUP_ID"]]
        group.setdefault(row["VARIABLE"], row["DATAVALUE"])
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (name, _), values in groups.items():
        result[name].append(values)
    return result


def _one(bif: dict[str, list[dict[str, str]]], group: str, path: Path):
    entries = bif.get(group, [])
    if len(entries) != 1:
        raise ProviderError(
            f"{path}: expected one {group} entry in the site BIF, found {len(entries)}"
        )
    return entries[0]


def _float(value: str | None) -> float | None:
    return None if value in (None, "") else float(value)


def _variables(text: str, path: Path) -> dict[str, Variable]:
    variables: dict[str, Variable] = {}
    for entry in _read_bif(text).get("GRP_VAR_INFO", []):
        name = entry["VAR_INFO_VARNAME"]
        variable = Variable(
            name=name,
            units=entry.get("VAR_INFO_UNIT", ""),
            definition=entry.get("VAR_INFO_DEFINITION", ""),
            height=_float(entry.get("VAR_INFO_HEIGHT")),
        )
        # A variable has one entry per period with its own sensor metadata.
        previous = variables.get(name)
        if previous is not None and (
            previous.units != variable.units
            or (name.startswith(("SWC_", "TS_")) and previous.height != variable.height)
        ):
            raise ProviderError(
                f"{path}: {name} changes unit or depth within the record, which "
                "xharvest cannot yet represent"
            )
        variables.setdefault(name, variable)
    return variables


def _columns(text: str, path: Path) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    if header[0] != "TIMESTAMP":
        raise ProviderError(f"{path}: the daily file does not start with TIMESTAMP")
    rows = list(reader)
    stamps = [row[0] for row in rows]
    dates = np.array(
        [f"{s[:4]}-{s[4:6]}-{s[6:8]}" for s in stamps], dtype="datetime64[D]"
    )
    values = np.array([row[1:] for row in rows], dtype=float).reshape(
        len(rows), len(header) - 1
    )
    values[values == FILL_VALUE] = np.nan
    return dates, {name: values[:, i] for i, name in enumerate(header[1:])}


_LICENCE = re.compile(r"shared under the (\S+) (?:data use )?license")


def read_daily(path: str | PathLike) -> Archive:
    """Read the daily file of a FLUXNET archive, without extracting it.

    Args:
        path: A FLUXNET ZIP archive.

    Returns:
        The site's daily data and metadata.

    Raises:
        ProviderError: If the archive lacks a file this needs, a data column
            has no `BIFVARINFO` entry, or the site metadata is ambiguous.
    """
    path = Path(path)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ProviderError(f"{path} is not a ZIP archive") from None
    with archive:
        data = _decode(archive.read(_member(archive, path, r"_FLUXMET_DD_.*\.csv$")))
        info = _decode(archive.read(_member(archive, path, r"_BIFVARINFO_DD_.*\.csv$")))
        site_bif = _decode(
            archive.read(_member(archive, path, r"_FLUXNET_BIF_.*\.csv$"))
        )
        policy = _decode(archive.read(_member(archive, path, r"^DATA_POLICY.*\.txt$")))

    dates, columns = _columns(data, path)
    variables = _variables(info, path)
    undescribed = [name for name in columns if name not in variables]
    if undescribed:
        raise ProviderError(f"{path}: no BIFVARINFO entry for {', '.join(undescribed)}")
    licence = _LICENCE.search(policy)
    if licence is None:
        raise ProviderError(f"{path}: cannot find the licence in the data policy")

    bif = _read_bif(site_bif)
    header = _one(bif, "GRP_HEADER", path)
    location = _one(bif, "GRP_LOCATION", path)
    oneflux = _one(bif, "GRP_ONEFLUX", path)
    lat, lon = (
        _float(location.get("LOCATION_LAT")),
        _float(location.get("LOCATION_LONG")),
    )
    offset = _float(_one(bif, "GRP_UTC_OFFSET", path).get("UTC_OFFSET"))
    if lat is None or lon is None or offset is None:
        raise ProviderError(f"{path}: the site BIF lacks a location or UTC offset")
    return Archive(
        site=header["SITE_ID"],
        site_name=header.get("SITE_NAME", ""),
        lat=lat,
        lon=lon,
        elevation=_float(location.get("LOCATION_ELEV")),
        utc_offset=offset,
        igbp=_one(bif, "GRP_IGBP", path).get("IGBP", ""),
        network=oneflux.get("PRODUCT_SOURCE_NETWORK", ""),
        processing_center=oneflux.get("PRODUCT_PROCESSING_CENTER", ""),
        oneflux_version=oneflux.get("PRODUCT_ONEFLUX_VERSION", ""),
        licence=licence[1],
        dates=dates,
        columns=columns,
        variables=variables,
    )
