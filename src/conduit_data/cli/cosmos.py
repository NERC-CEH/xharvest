"""``conduit-data cosmos``: COSMOS-UK site data."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from .. import cosmos
from ..errors import ProviderError

app = typer.Typer(
    help="COSMOS-UK soil moisture and meteorology (no credentials needed).",
    no_args_is_help=True,
)

CollectionOption = Annotated[
    str, typer.Option(help="'1D' for daily data, '30M' for 30-minute data.")
]


def _fail(err: Exception) -> typer.Exit:
    typer.echo(f"Error: {err}", err=True)
    return typer.Exit(1)


@app.command()
def sites(collection: CollectionOption = "1D") -> None:
    """List the sites, with their identifiers and periods of record."""
    try:
        found = cosmos.sites(collection)  # type: ignore[arg-type]
    except (ProviderError, ValueError) as err:
        raise _fail(err) from None
    for site in found:
        typer.echo(
            f"{site.id}\t{site.name}\t{site.lat:.5f}\t{site.lon:.5f}\t{site.period}"
        )


@app.command()
def fetch(
    site_ids: Annotated[list[str], typer.Argument(help="Site identifiers.")],
    start: Annotated[datetime, typer.Option(help="First timestamp (UTC).")],
    end: Annotated[datetime, typer.Option(help="Last timestamp (UTC), inclusive.")],
    out: Annotated[Path, typer.Option(help="Directory to write raw files to.")],
    parameter: Annotated[
        list[str] | None,
        typer.Option(help="Parameter to request; repeat for several. Default: all."),
    ] = None,
    collection: CollectionOption = "1D",
    overwrite: Annotated[
        bool, typer.Option(help="Download again even if a file exists.")
    ] = False,
) -> None:
    """Download raw CoverageJSON, one file per site, and print the paths."""
    try:
        paths = cosmos.fetch(
            site_ids,
            start,
            end,
            out,
            parameters=parameter,
            collection=collection,  # type: ignore[arg-type]
            overwrite=overwrite,
        )
    except (ProviderError, ValueError) as err:
        raise _fail(err) from None
    for path in paths:
        typer.echo(path)


@app.command()
def standardise(
    paths: Annotated[list[Path], typer.Argument(help="Raw files written by `fetch`.")],
    out: Annotated[Path, typer.Option(help="netCDF file to write.")],
) -> None:
    """Combine raw files into one standardised netCDF file."""
    try:
        written = cosmos.to_netcdf(paths, out)
    except (ProviderError, ValueError, FileNotFoundError) as err:
        raise _fail(err) from None
    typer.echo(written)
