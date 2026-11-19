"""Griffe extension that shows each standardisation node's `action` in its docs.

Nodes carry their action in a Hamilton decorator, `@tag(action="checks")` (see
ADR 2). This extension reads it from the source and opens the node's docstring
with it, so the rendered reference says what kind of thing each node does without
the docstring repeating the tag.
"""

import ast
from typing import Any

import griffe


def _action(decorator: griffe.Decorator) -> str | None:
    try:
        call = ast.parse(str(decorator.value), mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(call, ast.Call) or getattr(call.func, "id", None) != "tag":
        return None
    for keyword in call.keywords:
        if keyword.arg == "action" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return None


class ActionsExtension(griffe.Extension):
    """Open each tagged node's docstring with its action."""

    def on_function_instance(self, *, func: griffe.Function, **kwargs: Any) -> None:
        """Prepend `Action: <action>.` to the docstring of a tagged node."""
        actions = [a for d in func.decorators if (a := _action(d))]
        if not actions or func.docstring is None:
            return
        func.docstring.value = f"**Action: `{actions[0]}`.** {func.docstring.value}"
