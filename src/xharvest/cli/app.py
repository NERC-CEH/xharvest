"""The top-level `xharvest` command and its provider groups."""

import typer

from .cosmos import app as cosmos_app
from .fluxnet import app as fluxnet_app
from .icos import app as icos_app

app = typer.Typer(
    help="Download and standardise environmental data for catena and xarray.",
    no_args_is_help=True,
)
app.add_typer(cosmos_app, name="cosmos")
app.add_typer(fluxnet_app, name="fluxnet")
app.add_typer(icos_app, name="icos")
