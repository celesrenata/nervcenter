"""Migration entry point for the NerveCenter persistence layer.

``python -m backend.persistence.migrate`` runs ``alembic upgrade head``
against the URL in ``NERVECENTER_DATABASE_URL`` (fallback: the dev default
from :mod:`backend.persistence.connection`). The wrapper exists so the
container Job entrypoint does not need an ``alembic.ini`` next to its working
directory, or the ``alembic`` console script on ``$PATH``: the package is
installed via ``pip install .``, so the alembic environment lives inside
``site-packages`` and ``NERVE_ALEMBIC_SCRIPT_LOCATION`` names it explicitly.

This is intentionally a thin wrapper over alembic — no migration logic
lives here.
"""

from __future__ import annotations

import os
import pathlib
import sys

from alembic import command
from alembic.config import Config


def _script_location() -> pathlib.Path:
    """Return the installed ``alembic/`` environment directory."""

    override = os.environ.get("NERVE_ALEMBIC_SCRIPT_LOCATION")
    if override:
        return pathlib.Path(override)
    return pathlib.Path(__file__).resolve().parent / "alembic"


def _build_config() -> Config:
    """Build an Alembic :class:`Config` bound to the installed environment."""

    from backend.persistence.connection import (
        DEFAULT_DATABASE_URL,
        ENV_DATABASE_URL,
    )

    config = Config()
    config.set_main_option("script_location", str(_script_location()))
    url = os.environ.get(ENV_DATABASE_URL) or DEFAULT_DATABASE_URL
    config.set_main_option("sqlalchemy.url", url)
    return config


def main(argv: list[str] | None = None) -> int:
    """Run alembic for ``upgrade`` / ``current`` / ``heads`` / ``history``.

    ``upgrade`` (default) runs ``alembic upgrade head``.
    """

    args = list(argv) if argv is not None else sys.argv[1:]
    action = args[0] if args else "upgrade"
    config = _build_config()

    if action == "upgrade":
        command.upgrade(config, "head")
        print("nervcenter.migrate: upgraded to head")
        return 0
    if action == "current":
        command.current(config, verbose=True)
        return 0
    if action == "heads":
        command.heads(config, verbose=True)
        return 0
    if action == "history":
        command.history(config, verbose=True)
        return 0

    print(
        f"nervcenter.migrate: unknown action {action!r}; "
        "expected upgrade|current|heads|history",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
