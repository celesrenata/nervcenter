"""NerveCenter CLI package.

The ``cli`` group object is imported lazily so that ``python -m cli.main``
does not pre-import ``cli.main`` into ``sys.modules`` (runpy would then warn
about executing an already-imported module).
"""
from typing import Any

__all__ = ["cli"]


def __getattr__(name: str) -> Any:
    if name == "cli":
        from .main import cli as _cli

        return _cli
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
