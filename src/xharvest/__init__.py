"""Harvest environmental data from many providers into xarray-ready netCDF.

Each provider is a subpackage, for example `xharvest.cosmos` for COSMOS-UK.
A connector downloads raw provider files (`fetch`) and converts them into
standardised netCDF that conduit reads as-is (`standardise`). Some also provide
contract-annotated node functions for preparation specific to the source, which
conduit finds through its `conduit.modules` entry point.

Third-party dependencies of each provider sit behind an install extra named after
it, e.g. `pip install xharvest[cosmos]`.
"""

from importlib.metadata import version

__version__ = version("xharvest")

__all__ = ["__version__"]
