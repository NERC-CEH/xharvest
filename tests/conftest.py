import json
import re
import zipfile
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

    @property
    def data_requests(self) -> list[httpx.Request]:
        """Requests for a site's data, leaving out the site list."""
        return [r for r in self.requests if len(r.url.path.strip("/").split("/")) == 4]

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def cosmos_api():
    return CosmosAPI()


def load_json(path):
    return json.loads(Path(path).read_text())


ICOS_FIXTURES = Path(__file__).parent / "fixtures" / "icos"


@pytest.fixture
def icos_raw(tmp_path):
    """Copies of the trimmed ICOS FLUXNET archives and their sidecars."""
    paths = []
    for src in sorted(ICOS_FIXTURES.glob("*.zip")):
        sidecar = src.with_name(src.stem + ".meta.json")
        (tmp_path / sidecar.name).write_bytes(sidecar.read_bytes())
        (tmp_path / src.name).write_bytes(src.read_bytes())
        paths.append(tmp_path / src.name)
    return paths


class IcosPortal:
    """A stand-in for the ICOS Carbon Portal, serving the fixture archives.

    The site list is the real one, except that each archive's SHA-256 is that of
    the trimmed fixture it serves, unless `corrupt` names the site.
    """

    def __init__(self, corrupt: str | None = None):
        from xharvest.icos._fetch import sha256

        self.requests: list[httpx.Request] = []
        self.sites = load_json(ICOS_FIXTURES / "sites.json")
        self.archives: dict[str, bytes] = {}
        for binding in self.sites["results"]["bindings"]:
            object_id = binding["dobj"]["value"].rsplit("/", 1)[-1]
            content = (ICOS_FIXTURES / binding["fileName"]["value"]).read_bytes()
            self.archives[object_id] = content
            if binding["siteId"]["value"] != corrupt:
                binding["sha256"]["value"] = sha256(content)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "meta.icos-cp.eu" and request.url.path == "/sparql":
            return httpx.Response(200, json=self.sites)
        if request.url.path == "/licence_accept":
            (object_id,) = json.loads(request.url.params["ids"])
            return httpx.Response(
                302,
                headers={
                    "Location": f"/objects/{object_id}",
                    "Set-Cookie": f"CpLicenseAcceptedFor={object_id}; "
                    f"Path=/objects/{object_id}",
                },
            )
        if request.url.path.startswith("/objects/"):
            object_id = request.url.path.rsplit("/", 1)[-1]
            if request.headers.get("cookie") != f"CpLicenseAcceptedFor={object_id}":
                return httpx.Response(
                    302, headers={"Location": f"/licence?ids=%5B%22{object_id}%22%5D"}
                )
            return httpx.Response(200, content=self.archives[object_id])
        return httpx.Response(404, text="Not found")

    @property
    def downloads(self) -> list[httpx.Request]:
        """Requests that returned an archive."""
        return [r for r in self.requests if r.url.path.startswith("/objects/")]

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def icos_portal():
    return IcosPortal()


@pytest.fixture
def make_icos_portal():
    """`IcosPortal` itself, for a test that needs one set up differently."""
    return IcosPortal


def _rewrite_archive(source: Path, dest: Path, pattern: str, change) -> Path:
    """Copy an archive, passing the text of members matching `pattern` to `change`.

    `change` returns the new text, or None to leave the member out.
    """
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(dest, "w") as out:
        for info in src.infolist():
            raw = src.read(info)
            if re.search(pattern, info.filename):
                text = change(raw.decode("latin-1"))
                if text is None:
                    continue
                raw = text.encode("latin-1")
            out.writestr(info, raw)
    return dest


@pytest.fixture
def rewrite_archive():
    """Make a changed copy of a FLUXNET archive, for testing how errors are met."""
    return _rewrite_archive
