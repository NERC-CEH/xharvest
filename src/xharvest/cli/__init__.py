"""The ``xharvest`` command-line interface.

Each provider is a command group, e.g. ``xharvest cosmos fetch``. Every
command calls the provider's Python API and adds nothing to it.
"""

from .app import app


def main() -> None:
    """Run the ``xharvest`` command."""
    app()
