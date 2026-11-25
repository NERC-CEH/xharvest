"""`xharvest icos`: ICOS ecosystem stations' ancillary measurements."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from .. import icos
from ..errors import ProviderError

app = typer.Typer(
    help="ICOS ecosystem stations' LAI, biomass, canopy height and soil "
    "measurements, from the ICOS Carbon Portal (no credentials needed).",
    no_args_is_help=True,
)


class Group(StrEnum):
    """The groups `xharvest.icos.GROUPS` lists, as choices for `--group`."""

    LAI = "LAI"
    BIOMASS = "BIOMASS"
    HEIGHTC = "HEIGHTC"
    SOIL_TEX = "SOIL_TEX"
    SOIL_STOCK = "SOIL_STOCK"


def _fail(err: Exception) -> typer.Exit:
    typer.echo(f"Error: {err}", err=True)
    return typer.Exit(1)


@app.command()
def stations() -> None:
    """List the stations with an ETC L2 archive, and the archive's file name."""
    try:
        found = icos.stations()
    except ProviderError as err:
        raise _fail(err) from None
    for station in found:
        lat = "" if station.lat is None else f"{station.lat:.5f}"
        lon = "" if station.lon is None else f"{station.lon:.5f}"
        typer.echo(f"{station.id}\t{station.name}\t{lat}\t{lon}\t{station.file_name}")


@app.command()
def fetch(
    station_ids: Annotated[list[str], typer.Argument(help="ICOS station codes.")],
    out: Annotated[Path, typer.Option(help="Directory to write archives to.")],
    overwrite: Annotated[
        bool, typer.Option(help="Download again even if a file exists.")
    ] = False,
) -> None:
    """Download each station's whole ETC L2 archive, and print the paths."""
    try:
        paths = icos.fetch(station_ids, out, overwrite=overwrite)
    except (ProviderError, ValueError) as err:
        raise _fail(err) from None
    for path in paths:
        typer.echo(path)


@app.command()
def standardise(
    paths: Annotated[
        list[Path], typer.Argument(help="Archives from `fetch`; sidecars are skipped.")
    ],
    group: Annotated[Group, typer.Option(help="The group of measurements.")],
    out: Annotated[Path, typer.Option(help="netCDF file to write.")],
) -> None:
    """Standardise one group of the archives' ancillary measurements to netCDF."""
    try:
        written = icos.to_netcdf(paths, out, group.value)
    except (ProviderError, ValueError, FileNotFoundError) as err:
        raise _fail(err) from None
    typer.echo(written)
