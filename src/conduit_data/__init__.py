"""Data connectors for conduit and xarray.

Each provider is a subpackage, for example `conduit_data.cosmos` for COSMOS-UK.
A connector downloads raw provider files (`fetch`) and converts them into
standardised netCDF that conduit reads as-is (`standardise`). Some also provide
contract-annotated node functions for preparation specific to the source, which
conduit finds through its `conduit.modules` entry point.

Third-party dependencies of each provider sit behind an install extra named after
it, e.g. ``pip install conduit-data[cosmos]``.
"""

from importlib.metadata import version

__version__ = version("conduit-data")

__all__ = ["__version__"]
