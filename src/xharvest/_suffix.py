"""Name a connector's nodes after the suffix its input section uses.

catena names a loaded variable `{var}{suffix}`. A node that reads `snow` must
therefore read `snow_cosmos` once the input section sets `suffix = "_cosmos"`,
which is how two providers' files with a variable in common stay apart. Every node
in a connector's node module carries `follows_suffix`, so its output and its data
inputs all take the suffix the config gives under `<provider>_suffix`, and edges
between the module's own nodes still meet.

Hamilton is not a dependency of xharvest: node modules are for catena, which
provides it. Importing one without Hamilton raises an `ImportError` that says so.
"""

import inspect
from collections.abc import Callable
from typing import Any

try:
    from hamilton.function_modifiers import (
        ResolveAt,
        parameterize,
        resolve,
        source,
    )
    from hamilton.function_modifiers.dependencies import ParametrizedDependency
except ImportError as err:
    raise ImportError(
        "xharvest's node modules are for catena pipelines and need Hamilton, "
        "which catena provides: install catena "
        "(`pip install git+https://github.com/NERC-CEH/catena`), or "
        "Hamilton alone (`pip install apache-hamilton`) to build the nodes "
        "without catena. The standardised data does not need either."
    ) from err


def follows_suffix(key: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Append the suffix in config `key` to a node's name and its data inputs.

    With `key` unset or empty, the node keeps its own name and reads the bare
    variable names, as a config with `suffix = ""` loads them. Keyword-only
    parameters are settings, not data, and keep their names. The function itself
    is unchanged, so it can still be called directly.

    Hamilton applies this when the driver is built, through `resolve`, which needs
    power-user mode; catena enables it.

    Args:
        key: The config key holding the suffix, e.g. `"cosmos_suffix"`.

    Returns:
        A decorator for a node function.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        data = [
            p.name
            for p in inspect.signature(fn).parameters.values()
            if p.kind is not inspect.Parameter.KEYWORD_ONLY
        ]

        def decorate_with(**config: str) -> parameterize:
            suffix = config.get(key, "")
            inputs: dict[str, ParametrizedDependency] = {
                p: source(p + suffix) for p in data
            }
            return parameterize(**{fn.__name__ + suffix: inputs})

        decorate_with.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            [inspect.Parameter(key, inspect.Parameter.KEYWORD_ONLY, default="")]
        )
        return resolve(when=ResolveAt.CONFIG_AVAILABLE, decorate_with=decorate_with)(fn)

    return decorator
