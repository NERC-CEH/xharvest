"""The ``conduit-data`` command-line interface.

Each provider is a command group, e.g. ``conduit-data cosmos fetch``. Every
command calls the provider's Python API and adds nothing to it. The CLI needs the
``cli`` extra (``pip install conduit-data[cli]``).
"""

from .._extras import require


def main() -> None:
    """Run the ``conduit-data`` command."""
    require("typer", "cli")
    from .app import app

    app()
