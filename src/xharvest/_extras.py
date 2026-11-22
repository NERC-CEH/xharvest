"""Lazy imports of dependencies that sit behind an install extra."""

import importlib
from types import ModuleType

SOURCE = "git+https://github.com/NERC-CEH/xharvest"
"""Where to install xharvest from, as it is not on PyPI."""


def require(module: str, extra: str) -> ModuleType:
    """Import `module`, or explain which extra provides it.

    Args:
        module: The module to import, e.g. `"httpx"`.
        extra: The install extra that provides it, e.g. `"cosmos"`.

    Returns:
        The imported module.

    Raises:
        ImportError: If the module is not installed. The message names the extra.
    """
    try:
        return importlib.import_module(module)
    except ImportError as err:
        raise ImportError(
            f"{module!r} is not installed; install it with "
            f'`pip install "xharvest[{extra}] @ {SOURCE}"`'
        ) from err
