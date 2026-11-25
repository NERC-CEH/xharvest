"""Standardise ICOS ETC L2 archives' ancillary measurements, one group at a time.

`standardise` runs a Hamilton graph built from the nodes in
`xharvest.icos._pipeline`. Each node does one thing, which its docstring and
`action` tag say; the provider page draws the graph and lists the nodes.

Only the groups in `GROUPS` are read: LAI, biomass, canopy height, soil texture
and soil stocks.

Examples:
    >>> from pathlib import Path
    >>> from xharvest.icos import to_netcdf
    >>> paths = Path("data/raw").glob("*.zip")
    >>> to_netcdf(paths, "data/lai.nc", "LAI")  # doctest: +SKIP
"""

from collections.abc import Iterable
from os import PathLike
from pathlib import Path

import xarray as xr

from .. import _graph
from . import _pipeline

MODULES = (_pipeline,)
"""The node modules `standardise` builds its graph from."""

OUTPUT = "datasets"
"""The node `standardise` computes: one Dataset per group."""


def standardise(paths: Iterable[str | PathLike], group: str) -> xr.Dataset:
    """Combine one group of ancillary measurements from ETC L2 archives.

    Args:
        paths: ZIP archives written by `xharvest.icos.fetch`. Provenance
            sidecars among them are skipped, so a glob over the download
            directory works.
        group: A group in `GROUPS`, e.g. `"LAI"` or `"SOIL_TEX"`.

    Returns:
        A Dataset with one dim, `record`: one record per measurement, from
        every station. The group's values are data variables; the station, its
        location, the measurement's `time` and `time_bounds`, and every
        qualifier the archive gives (type, statistic, method, species, depth,
        ...) are coordinates on `record`, to select on.

    Raises:
        ValueError: If `group` is not in `GROUPS`, or no archives are given.
        FileNotFoundError: If an archive has no provenance sidecar.
        ProviderError: If an archive is not one the connector can read, or a
            value is not a number or has a unit the connector does not know.
    """
    if group not in _pipeline.GROUPS:
        raise ValueError(
            f"unknown group {group!r}; choose from {', '.join(_pipeline.GROUPS)}"
        )
    datasets = _graph.run(MODULES, OUTPUT, paths=[Path(p) for p in paths])
    return datasets[group]


def to_netcdf(paths: Iterable[str | PathLike], out: str | PathLike, group: str) -> Path:
    """Standardise one group of ancillary measurements and write it to netCDF.

    Args:
        paths: As for `standardise`.
        out: The netCDF file to write; its directory is created if missing.
        group: As for `standardise`.

    Returns:
        The path written.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    standardise(paths, group).to_netcdf(out)
    return out
