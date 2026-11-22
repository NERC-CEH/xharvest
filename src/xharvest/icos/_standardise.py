"""Standardise FLUXNET archives from the ICOS Carbon Portal into one Dataset.

`standardise` runs a Hamilton graph built from the nodes in
`xharvest.icos._pipeline` and the FLUXNET reader, `xharvest.icos._fluxnet`. Each
node does one thing, which its docstring and `action` tag say; the provider page
draws the graph and lists the nodes.

Only the daily (`DD`) files are read, and only a fixed set of variables for soil
moisture and ecosystem carbon modelling: see `VARIABLES`.

Examples:
    >>> from pathlib import Path
    >>> from xharvest.icos import to_netcdf
    >>> to_netcdf(Path("data/icos").glob("*.zip"), "data/icos.nc")  # doctest: +SKIP
"""

from collections.abc import Iterable
from os import PathLike
from pathlib import Path

import xarray as xr

from .. import _graph
from . import _fluxnet, _pipeline

MODULES = (_fluxnet, _pipeline)
"""The node modules `standardise` builds its graph from."""


def standardise(paths: Iterable[str | PathLike]) -> xr.Dataset:
    """Combine FLUXNET archives from the ICOS Carbon Portal into one daily Dataset.

    Args:
        paths: ZIP archives written by `xharvest.icos.fetch`. Provenance
            sidecars among them are skipped, so a glob over the download
            directory works.

    Returns:
        A Dataset with dims `(time, site, depth)`. `depth` is the union of the
        sites' soil sensor depths, in metres below ground; only the soil
        profiles use it. Sites are outer-joined on time and depth, so a site
        with a shorter record or fewer sensors is NaN-padded, and a variable a
        site does not measure is NaN there.

    Raises:
        ValueError: If no archives are given, the sites' UTC offsets differ, or
            two archives for one site disagree where they overlap.
        FileNotFoundError: If an archive has no provenance sidecar.
        ProviderError: If an archive is not one the connector can read, or a
            kept variable has a unit other than the one standardise expects.
    """
    return _graph.run(MODULES, "dataset", paths=[Path(p) for p in paths])


def to_netcdf(paths: Iterable[str | PathLike], out: str | PathLike) -> Path:
    """Standardise FLUXNET archives and write the result to netCDF.

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
