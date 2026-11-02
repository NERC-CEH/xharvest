"""COSMOS-UK: daily and 30-minute soil moisture and meteorology at UK sites.

COSMOS-UK is the UK Centre for Ecology & Hydrology's network of cosmic-ray soil
moisture sites. Data come from the COSMOS-UK API, which needs no credentials, and
are licensed under the Open Government Licence.

- `sites` lists the sites, and `fetch` downloads raw CoverageJSON per site.
- `standardise` combines raw files into a ``(time, site)`` Dataset, and
  `to_netcdf` writes it to a file conduit can read.
- `xharvest.cosmos.nodes` holds node functions that conduit finds under the
  section name ``[cosmos]``.

`fetch` and `sites` need the ``cosmos`` extra (``pip install xharvest[cosmos]``).

Example:
    >>> from datetime import date
    >>> from xharvest import cosmos
    >>> raw = cosmos.fetch("ALIC1", date(2025, 1, 1), date(2025, 1, 31),
    ...                    "data/raw")  # doctest: +SKIP
    >>> cosmos.to_netcdf(raw, "data/cosmos.nc")  # doctest: +SKIP
"""

from .fetch import API_URL, COLLECTIONS, Collection, Site, fetch, sites
from .standardise import standardise, to_netcdf

__all__ = [
    "API_URL",
    "COLLECTIONS",
    "Collection",
    "Site",
    "fetch",
    "sites",
    "standardise",
    "to_netcdf",
]
