"""The ``conduit-data`` command-line interface.

Each provider is a command group, e.g. ``conduit-data cosmos fetch``. Every
command calls the provider's Python API and adds nothing to it.
"""

from .app import app


def main() -> None:
    """Run the ``conduit-data`` command."""
    app()
