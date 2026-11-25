"""Calls the real ICOS Carbon Portal. Run with ``just test-live``.

Downloads UK-AMo's whole ETC L2 archive (about 85 MB) once. Its SHA-256 has both
`+` and `/`, so this also checks `fetch` compares hashes in the portal's form.
"""

import pytest

from xharvest import icos

pytestmark = pytest.mark.live

STATION = "UK-AMo"


@pytest.fixture(scope="module")
def archive_path(tmp_path_factory):
    (path,) = icos.fetch(STATION, tmp_path_factory.mktemp("icos"))
    return path


def test_stations():
    found = {s.id: s for s in icos.stations()}
    assert len(found) > 80
    assert found[STATION].name == "Auchencorth Moss"
    assert "creativecommons.org/licenses/by/4.0" in found[STATION].licence


def test_fetch_and_standardise(archive_path):
    # UK-AMo measures vegetation, but has published no soil groups.
    lai = icos.standardise([archive_path], "LAI")
    assert lai.sizes["record"] > 100
    assert lai.time.notnull().all()
    assert icos.standardise([archive_path], "BIOMASS").sizes["record"] > 0
    assert icos.standardise([archive_path], "SOIL_TEX").sizes["record"] == 0
