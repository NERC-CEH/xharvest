"""Convert COSMOS-UK CoverageJSON into a standardised xarray Dataset.

`standardise` runs a Hamilton graph built from the nodes in
`xharvest.cosmos._pipeline`. Each node does one thing, which its docstring and
`action` tag say; the provider page draws the graph and lists the nodes.

Examples:
    >>> from pathlib import Path
    >>> from xharvest.cosmos import to_netcdf
    >>> to_netcdf(Path("data/cosmos").glob("*_1D_*.json"),
    ...           "data/cosmos_1D.nc")  # doctest: +SKIP
"""

from collections.abc import Iterable
from os import PathLike
from pathlib import Path

import xarray as xr

from .. import _graph
from . import _pipeline

MODULES = (_pipeline,)
"""The node modules `standardise` builds its graph from."""


def standardise(paths: Iterable[str | PathLike]) -> xr.Dataset:
    """Combine raw COSMOS-UK files into one standardised Dataset.

    Args:
        paths: CoverageJSON files written by `xharvest.cosmos.fetch`, all from
            the same collection. Provenance sidecars among them are skipped, so a
            glob over the download directory works.

    Returns:
        A Dataset with dims `(time, site)`, with `site_name`, `lat`, `lon` and
        `altitude` coordinates per site, one variable per API parameter, and
        `time_bounds`, the period each value covers. Files for one site that
        cover different periods are joined into one record. Sites are
        outer-joined on time, so a site with a shorter record is NaN-padded.

    Raises:
        ValueError: If no files are given, they mix collections, a sidecar
            lacks the collection or a site name, or two files for one site
            disagree where they overlap.
        FileNotFoundError: If a file has no provenance sidecar.
        ProviderError: If a file is not a COSMOS-UK response the connector can read.
    """
    return _graph.run(MODULES, "dataset", paths=[Path(p) for p in paths])


def to_netcdf(paths: Iterable[str | PathLike], out: str | PathLike) -> Path:
    """Standardise raw COSMOS-UK files and write the result to netCDF.

    Args:
        paths: As for `standardise`.
        out: The netCDF file to write; its directory is created if missing.

    Returns:
        The path written.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    standardise(paths).to_netcdf(out)
    return out
