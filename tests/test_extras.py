import importlib
import sys
from datetime import date

import pytest

from conduit_data._extras import require


def test_require_returns_the_module():
    assert require("json", "unused").__name__ == "json"


def test_require_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", None)
    with pytest.raises(ImportError, match=r"pip install conduit-data\[cosmos\]"):
        require("httpx", "cosmos")


def test_cosmos_imports_without_httpx_but_fetch_needs_it(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "httpx", None)
    for name in [m for m in sys.modules if m.startswith("conduit_data.cosmos")]:
        monkeypatch.delitem(sys.modules, name)
    cosmos = importlib.import_module("conduit_data.cosmos")
    with pytest.raises(ImportError, match=r"conduit-data\[cosmos\]"):
        cosmos.fetch("ALIC1", date(2025, 1, 1), date(2025, 1, 2), tmp_path)
