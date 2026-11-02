"""Regenerate the COSMOS-UK test fixtures from the live API.

Run by hand, from the repository root, when the fixtures need refreshing:

    uv run python tests/fixtures/cosmos/make_fixtures.py

The windows are chosen so the fixtures cover what the tests rely on:

- MOORH has snow days from 2025-01-05 to 2025-01-13;
- the two sites' windows differ, so combining them pads each with NaN;
- ``tdt3_vwc`` is entirely null at ALIC1, which has no TDT sensor 3;
- ``albedo`` is aggregated over 4 hours, not the whole day;
- ``snow`` is instantaneous.
"""

import json
from datetime import date
from pathlib import Path

import httpx

from xharvest.cosmos import fetch
from xharvest.cosmos._fetch import API_URL

HERE = Path(__file__).parent
SITES = {
    "MOORH": (date(2025, 1, 1), date(2025, 1, 14)),
    "ALIC1": (date(2025, 1, 4), date(2025, 1, 17)),
}
PARAMETERS = ["albedo", "cosmos_vwc", "d86_75m", "precip", "snow", "ta", "tdt3_vwc"]


def main() -> None:
    """Fetch the site files and a trimmed copy of the site list."""
    for site, (start, end) in SITES.items():
        fetch(site, start, end, HERE, parameters=PARAMETERS, overwrite=True)

    locations = httpx.get(f"{API_URL}/collections/1D/locations", timeout=120).json()
    locations["features"] = [f for f in locations["features"] if f["id"] in SITES]
    for feature in locations["features"]:
        feature["properties"]["parameter-name"] = PARAMETERS
    locations.pop("parameters", None)
    (HERE / "locations_1D.json").write_text(json.dumps(locations, indent=1) + "\n")


if __name__ == "__main__":
    main()
