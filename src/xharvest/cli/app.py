"""The top-level `xharvest` command and its provider groups."""

import typer

from .cosmos import app as cosmos_app

app = typer.Typer(
    help="Download and standardise environmental data for catena and xarray.",
    no_args_is_help=True,
)
app.add_typer(cosmos_app, name="cosmos")
