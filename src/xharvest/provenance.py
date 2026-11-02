"""Provenance sidecars and the provenance attributes of standardised output.

A fetch writes a sidecar next to each raw file, recording the request and when it
was made, because raw provider files rarely record either. Standardisation reads
the sidecar and writes the provenance onto the dataset as CF/ACDD global
attributes:

- `institution`: who produces the data;
- `source`: the service the data came from;
- `license`: the licence the provider states;
- `history`: one line per retrieval and one for standardisation, each starting
  with a UTC timestamp.

Examples:
    >>> from pathlib import Path
    >>> sidecar_path(Path("ALIC1_1D_20250101_20250105.json"))
    PosixPath('ALIC1_1D_20250101_20250105.meta.json')
"""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from os import PathLike
from pathlib import Path
from typing import Any

from . import __version__

PROVENANCE_ATTRS = ("institution", "source", "license", "history")
"""Global attributes every standardised dataset carries."""

SIDECAR_SUFFIX = ".meta.json"


@dataclass(frozen=True)
class Retrieval:
    """One request to a provider, as recorded in a sidecar.

    Attributes:
        url: The URL requested, without the query string.
        params: The query parameters sent.
        retrieved: When the response was received, as an ISO 8601 UTC timestamp.
        agent: The package and version that made the request.
        metadata: Facts about the data the response itself omits, e.g. site names.
    """

    url: str
    params: dict[str, Any]
    retrieved: str
    agent: str
    metadata: dict[str, Any] = field(default_factory=dict)


def utc_now() -> str:
    """Return the current time as an ISO 8601 UTC timestamp, to the second."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sidecar_path(path: str | PathLike) -> Path:
    """Return the sidecar path for a raw data file."""
    path = Path(path)
    return path.with_name(path.stem + SIDECAR_SUFFIX)


def is_sidecar(path: str | PathLike) -> bool:
    """Whether `path` names a sidecar rather than a raw data file."""
    return Path(path).name.endswith(SIDECAR_SUFFIX)


def _replace(path: Path, content: bytes) -> None:
    # Write beside the target, then rename, so `path` is never left half-written.
    tmp = path.with_name(f".{path.name}.part")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save(
    path: str | PathLike,
    content: bytes,
    url: str,
    params: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Retrieval:
    """Write a provider's response to `path`, and its sidecar.

    Both files are written atomically, data first. The sidecar is written last,
    so it marks the download as complete: a data file without one is from a
    download that was interrupted.

    Args:
        path: The raw data file to write.
        content: The response body.
        url: The URL requested, without the query string.
        params: The query parameters sent.
        metadata: Facts about the data the response itself omits, for
            standardisation to use.

    Returns:
        The retrieval recorded.
    """
    path = Path(path)
    retrieval = Retrieval(
        url=url,
        params=params,
        retrieved=utc_now(),
        agent=f"xharvest {__version__}",
        metadata=metadata or {},
    )
    _replace(path, content)
    sidecar = json.dumps(asdict(retrieval), indent=2) + "\n"
    _replace(sidecar_path(path), sidecar.encode())
    return retrieval


def is_fetched(path: str | PathLike, url: str, params: dict[str, Any]) -> bool:
    """Whether `path` already holds the response to this request.

    Args:
        path: The raw data file a fetch would write.
        url: The URL the fetch would request, without the query string.
        params: The query parameters it would send.

    Returns:
        True if `path` and its sidecar exist and the sidecar records the same
        request; False if either is missing, so the file should be fetched.

    Raises:
        ValueError: If the sidecar records a different request, since fetching
            would replace data the caller may still want.
    """
    path = Path(path)
    if not (path.exists() and sidecar_path(path).exists()):
        return False
    recorded = read_sidecar(path)
    # Compare as JSON, which is how the sidecar stored them.
    requested = json.loads(json.dumps({"url": url, "params": params}))
    if {"url": recorded.url, "params": recorded.params} == requested:
        return True
    raise ValueError(
        f"{path} holds a different request ({history_line(recorded)}) from the "
        f"one asked for ({url}, {params}); pass overwrite=True to replace it, "
        "or fetch to another directory"
    )


def read_sidecar(path: str | PathLike) -> Retrieval:
    """Read the retrieval recorded for the raw data file `path`.

    Raises:
        FileNotFoundError: If the file has no sidecar, e.g. because it was not
            written by a connector's fetch.
    """
    sidecar = sidecar_path(path)
    if not sidecar.exists():
        raise FileNotFoundError(
            f"{path} has no provenance sidecar ({sidecar.name}); "
            "fetch it with the connector so its provenance is recorded"
        )
    return Retrieval(**json.loads(sidecar.read_text()))


def history_line(retrieval: Retrieval) -> str:
    """Describe a retrieval as one line of a CF `history` attribute."""
    query = "&".join(f"{k}={v}" for k, v in retrieval.params.items())
    url = f"{retrieval.url}?{query}" if query else retrieval.url
    return f"{retrieval.retrieved} retrieved {url} ({retrieval.agent})"
