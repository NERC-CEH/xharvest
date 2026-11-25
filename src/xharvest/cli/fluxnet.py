"""`xharvest fluxnet`: FLUXNET data from the ICOS Carbon Portal."""

from pathlib import Path
from typing import Annotated

import typer

from .. import fluxnet
from ..errors import ProviderError

app = typer.Typer(
    help="FLUXNET daily flux and meteorology from the ICOS Carbon Portal "
    "(no credentials needed).",
    no_args_is_help=True,
)


def _fail(err: Exception) -> typer.Exit:
    typer.echo(f"Error: {err}", err=True)
    return typer.Exit(1)


@app.command()
def sites() -> None:
    """List the sites with a FLUXNET archive, and the archive's file name."""
    try:
        found = fluxnet.sites()
    except ProviderError as err:
        raise _fail(err) from None
    for site in found:
        lat = "" if site.lat is None else f"{site.lat:.5f}"
        lon = "" if site.lon is None else f"{site.lon:.5f}"
        typer.echo(f"{site.id}\t{site.name}\t{lat}\t{lon}\t{site.file_name}")


@app.command()
def fetch(
    site_ids: Annotated[list[str], typer.Argument(help="FLUXNET site codes.")],
    out: Annotated[Path, typer.Option(help="Directory to write archives to.")],
    overwrite: Annotated[
        bool, typer.Option(help="Download again even if a file exists.")
    ] = False,
) -> None:
    """Download each site's whole FLUXNET archive, and print the paths."""
    try:
        paths = fluxnet.fetch(site_ids, out, overwrite=overwrite)
    except (ProviderError, ValueError) as err:
        raise _fail(err) from None
    for path in paths:
        typer.echo(path)


@app.command()
def standardise(
    paths: Annotated[
        list[Path], typer.Argument(help="Archives from `fetch`; sidecars are skipped.")
    ],
    out: Annotated[Path, typer.Option(help="netCDF file to write.")],
) -> None:
    """Standardise the archives' daily data into one netCDF file."""
    try:
        written = fluxnet.to_netcdf(paths, out)
    except (ProviderError, ValueError, FileNotFoundError) as err:
        raise _fail(err) from None
    typer.echo(written)
