"""Alembic configuration for NerveCenter.

This module bootstraps Alembic for the NerveCenter persistence layer. It reads
the database URL from ``NERVECENTER_DATABASE_URL`` (or the default) and
configures environment variables for the migration runner.

Usage
-----

Development / testing:

    alembic upgrade head

Create a new revision:

    alembic revision -m "description"

Run against a specific environment:

    NERVECENTER_DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" alembic upgrade head

Environment variables
---------------------
- ``NERVECENTER_DATABASE_URL`` — SQLAlchemy URL (required, or uses default).
- ``NERVECENTER_DB_ECHO`` — set to ``1`` to log all SQL statements.
- ``ALEMBIC_CONTEXT`` — internal marker used by Alembic.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection, create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from backend.persistence.connection import (
    DEFAULT_DATABASE_URL,
    ENV_DATABASE_URL,
)
from backend.persistence.models.base import Base

# --------------------------------------------
# Alembic Config
# --------------------------------------------

alembic_cfg = context.config

# Set the SQLAlchemy URL from environment if not already set
if not alembic_cfg.get_main_option("sqlalchemy.url", None):
    alembic_cfg.set_main_option("sqlalchemy.url", os.environ.get(ENV_DATABASE_URL, DEFAULT_DATABASE_URL))

# Import your models' metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the
    Engine creation we don't even need a DBAPI to be available.
    """
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = alembic_cfg.get_main_option("sqlalchemy.url")

    engine = create_async_engine(url, poolclass=pool.NullPool)

    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = alembic_cfg.get_main_option("sqlalchemy.url")

    if url.startswith("postgresql+asyncpg"):
        import asyncio

        asyncio.run(run_async_migrations())
    else:
        engine = create_engine(url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            do_run_migrations(connection)
        engine.dispose()


# --------------------------------------------
# Main entry point
# --------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
