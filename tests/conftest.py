import json
from pathlib import Path

import httpx
import pytest

COSMOS_FIXTURES = Path(__file__).parent / "fixtures" / "cosmos"


@pytest.fixture
def cosmos_raw(tmp_path):
    """Copies of the raw COSMOS-UK fixture files and their sidecars."""
    paths = []
    for src in sorted(COSMOS_FIXTURES.glob("*_1D_*.json")):
        dest = tmp_path / src.name
        dest.write_bytes(src.read_bytes())
        if not src.name.endswith(".meta.json"):
            paths.append(dest)
    return paths


class CosmosAPI:
    """A stand-in for the COSMOS-UK API, serving the fixture files."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = request.url.path.strip("/").split("/")
        if parts == ["collections", "1D", "locations"]:
            return httpx.Response(
                200, content=(COSMOS_FIXTURES / "locations_1D.json").read_bytes()
            )
        if parts[:3] == ["collections", "1D", "locations"] and len(parts) == 4:
            matches = sorted(COSMOS_FIXTURES.glob(f"{parts[3]}_1D_*[0-9].json"))
            if matches:
                return httpx.Response(200, content=matches[0].read_bytes())
        return httpx.Response(
            400,
            json={
                "code": 400,
                "name": "Bad Request",
                "description": f"Invalid location ID(s): ['{parts[-1]}'].",
            },
        )

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def cosmos_api():
    return CosmosAPI()


def load_json(path):
    return json.loads(Path(path).read_text())
