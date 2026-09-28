"""Async SQLAlchemy + asyncpg engine, session factory, and pgvector-aware health checks.

This module owns the *only* place in NerveCenter that touches the raw
PostgreSQL URL and pool configuration. Every subsystem that needs durable
storage should depend on :func:`create_persistence` (or the ``NERVECENTER_DATABASE_URL``
environment variable) rather than constructing an :class:`~sqlalchemy.ext.asyncio.AsyncEngine`
directly.

Key exports
-----------
- :class:`DatabaseConfig` — typed, frozen container of pool/dialect knobs.
- :func:`config_from_env` — build a config from process env (``NERVECENTER_DATABASE_URL``).
- :func:`create_engine` / :func:`create_persistence` — construct an engine and
  an :class:`~sqlalchemy.ext.asyncio.async_sessionmaker`.
- :func:`session_scope` — transaction-scoped async context manager.
- :func:`ensure_pgvector` — idempotently install the ``vector`` extension.
- :func:`check_health` — return a :class:`HealthReport` including server
  version, latency, pool counters, and pgvector availability.
- :data:`ENV_DATABASE_URL` / :data:`DEFAULT_DATABASE_URL` — env-var name and
  the dev default (``localhost:5432/nervcenter``).

The module is intentionally free of any import from
:mod:`backend.persistence.models` so that the connection layer can be used
before the models are imported (and so Alembic's env.py can import it
independently).
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal
from urllib.parse import urlsplit, urlunsplit

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

log = structlog.get_logger(__name__)

#: Environment variable that overrides the database URL when set.
ENV_DATABASE_URL = "NERVECENTER_DATABASE_URL"

#: Fallback used when ``ENV_DATABASE_URL`` is not set — matches the local
#: deployment default documented in ``deployments/local``.
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://nervcenter:nervcenter@localhost:5432/nervcenter"
)

#: Valid values for the SSL mode knob on the asyncpg connection.
SslMode = Literal["require", "prefer", "disable"]


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Immutable container of engine/pool configuration.

    Attributes
    ----------
    url:
        SQLAlchemy URL. Must use the ``postgresql+asyncpg`` dialect for this
        project (asyncpg is the only supported driver).
    pool_size / max_overflow / pool_recycle / pool_pre_ping:
        Standard SQLAlchemy pool knobs; see :mod:`sqlalchemy.pool` for details.
    echo:
        Emit all emitted SQL. ``False`` by default; enable for local debug only.
    connect_timeout:
        Seconds to wait for a TCP connection. ``None`` defers to the driver default.
    ssl_mode:
        Optional SSL posture. ``None`` means driver default (usually ``prefer``).
    """

    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 1800
    pool_pre_ping: bool = True
    echo: bool = False
    connect_timeout: int | None = 10
    ssl_mode: SslMode | None = None

    def __post_init__(self) -> None:  # pragma: no cover - validation only
        if not self.url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "NERVECENTER persistence requires the asyncpg dialect; "
                f"got {self.url.split('://', 1)[0]!r}. Expected 'postgresql+asyncpg://...'"
            )


def config_from_env() -> DatabaseConfig:
    """Build a :class:`DatabaseConfig` from the process environment.

    Reads ``NERVECENTER_DATABASE_URL``; falls back to :data:`DEFAULT_DATABASE_URL`
    if unset. Numeric overrides (pool size, timeout, ...) are read from
    ``NERVECENTER_DB_*`` variables when present.
    """

    url = os.environ.get(ENV_DATABASE_URL) or DEFAULT_DATABASE_URL

    def _int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            return default
        try:
            return int(raw)
        except ValueError:
            log.warning("persistence.config.bad_int", name=name, raw=raw, using_default=default)
            return default

    def _opt_int(name: str) -> int | None:
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    ssl_mode: SslMode | None
    ssl_raw = os.environ.get("NERVECENTER_DB_SSL_MODE")
    if ssl_raw:
        ssl_mode = SslMode(ssl_raw)  # type: ignore[call-arg]
    else:
        ssl_mode = None

    return DatabaseConfig(
        url=url,
        pool_size=_int("NERVECENTER_DB_POOL_SIZE", 10),
        max_overflow=_int("NERVECENTER_DB_MAX_OVERFLOW", 20),
        pool_recycle=_int("NERVECENTER_DB_POOL_RECYCLE", 1800),
        connect_timeout=_opt_int("NERVECENTER_DB_CONNECT_TIMEOUT"),
        ssl_mode=ssl_mode,
        echo=os.environ.get("NERVECENTER_DB_ECHO", "0") == "1",
    )


def redact_url(url: str) -> str:
    """Return ``url`` with any embedded password masked, for safe logging."""

    parts = urlsplit(url)
    if parts.password:
        parts = parts._replace(password="***")
    return urlunsplit(parts)


def create_engine(config: DatabaseConfig | None = None, *, url: str | None = None) -> AsyncEngine:
    """Create an :class:`AsyncEngine` bound to asyncpg.

    Parameters
    ----------
    config:
        A :class:`DatabaseConfig`; defaults to :func:`config_from_env`.
    url:
        If provided, ``config`` (or the env default) is cloned with this URL.
        Handy for tests that want to point at a temporary database.
    """

    cfg = config or config_from_env()
    if url is not None:
        cfg = DatabaseConfig(
            url=url,
            pool_size=cfg.pool_size,
            max_overflow=cfg.max_overflow,
            pool_recycle=cfg.pool_recycle,
            pool_pre_ping=cfg.pool_pre_ping,
            echo=cfg.echo,
            connect_timeout=cfg.connect_timeout,
            ssl_mode=cfg.ssl_mode,
        )

    connect_args: dict[str, Any] = {}
    if cfg.connect_timeout is not None:
        connect_args["timeout"] = cfg.connect_timeout
    if cfg.ssl_mode is not None:
        connect_args["ssl"] = cfg.ssl_mode == "require"

    engine = create_async_engine(
        cfg.url,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=cfg.pool_size,
        max_overflow=cfg.max_overflow,
        pool_recycle=cfg.pool_recycle,
        pool_pre_ping=cfg.pool_pre_ping,
        echo=cfg.echo,
        connect_args=connect_args or None,
    )
    log.info("persistence.engine_created", url=redact_url(cfg.url), pool_size=cfg.pool_size)
    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an :class:`async_sessionmaker` bound to ``engine``.

    ``expire_on_commit=False`` and ``autoflush=False`` are intentional:
    NerveCenter records are written with explicit ``flush()`` calls, and
    expired attribute access across await boundaries would be surprising.
    """

    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )


def create_persistence(
    config: DatabaseConfig | None = None, *, url: str | None = None
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Convenience: build both the engine and the session factory in one call."""

    engine = create_engine(config=config, url=url)
    return engine, make_session_factory(engine)


@asynccontextmanager
async def session_scope(
    engine: AsyncEngine,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction; commit on success, rollback on error.

    Usage::

        async with session_scope(engine) as session:
            session.add(entity)
            await session.flush()
        # committed here, outside the block
    """

    factory = session_factory or make_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def ensure_pgvector(conn_or_session) -> None:
    """Idempotently install the ``vector`` extension on the connected database.

    Must be run by a role with ``CREATE`` privilege on the target database
    (typically a superuser or the owner). Safe to call on every startup.
    """

    if isinstance(conn_or_session, AsyncSession):
        async with conn_or_session.connection() as conn:
            await _run_create_extension(conn)
    else:
        await _run_create_extension(conn_or_session)


async def _run_create_extension(conn) -> None:
    await conn.run_sync(lambda sync_conn: sync_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;")))


async def pgvector_available(conn_or_session) -> bool:
    """Return ``True`` when the ``vector`` extension is present in the connected database."""

    async def _probe(sync_conn) -> bool:
        result = await sync_conn.exec_driver_sql(  # type: ignore[attr-defined]
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        )
        return result.first() is not None

    # asyncpg uses its own sync connection shim; run_sync is the portable path.
    async def _probe_sync(sync_conn) -> bool:
        rows = sync_conn.exec_driver_sql("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchall()
        return bool(rows)

    if isinstance(conn_or_session, AsyncSession):
        async with conn_or_session.connection() as conn:
            return await conn.run_sync(_probe_sync)
    return await conn_or_session.run_sync(_probe_sync)


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Structured result of :func:`check_health`.

    ``status`` is one of:

    - ``"healthy"`` — connected, ``SELECT 1`` succeeded, and pgvector is installed.
    - ``"degraded"`` — connected but pgvector extension is missing (call
      :func:`ensure_pgvector` before relying on vector queries).
    - ``"unhealthy"`` — no connection could be established.
    """

    status: Literal["healthy", "degraded", "unhealthy"]
    ok: bool
    latency_ms: float
    server_version: str | None
    database: str | None
    pgvector_available: bool
    pool_in_use: int | None
    pool_overflow: int | None
    pool_checkedout: int | None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.ok,
            "latency_ms": round(self.latency_ms, 3),
            "server_version": self.server_version,
            "database": self.database,
            "pgvector_available": self.pgvector_available,
            "pool": {
                "in_use": self.pool_in_use,
                "overflow": self.pool_overflow,
                "checkedout": self.pool_checkedout,
            },
            "error": self.error,
        }


async def check_health(engine: AsyncEngine) -> HealthReport:
    """Probe the database and return a :class:`HealthReport`.

    Performs three statements on a single connection:

    1. ``SELECT 1`` — connectivity + latency measurement.
    2. ``SELECT version()`` — server banner (returned verbatim; may be useful
       for ops).
    3. ``SELECT 1 FROM pg_extension WHERE extname = 'vector'`` — pgvector probe.

    The report also snapshots pool counters (best effort; ``None`` when the
    pool class does not expose them).
    """

    pool = engine.pool
    pool_snapshot = _snapshot_pool(pool)

    t0 = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            latency_ms = (time.perf_counter() - t0) * 1000.0

            version_row = await conn.execute(text("SELECT version()"))
            server_version: str | None = version_row.scalar()

            db_row = await conn.execute(text("SELECT current_database()"))
            database: str | None = db_row.scalar()

            probe = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            pgvector = probe.first() is not None

            status: Literal["healthy", "degraded"] = "healthy" if pgvector else "degraded"
            return HealthReport(
                status=status,
                ok=True,
                latency_ms=latency_ms,
                server_version=server_version,
                database=database,
                pgvector_available=pgvector,
                **pool_snapshot,  # type: ignore[misc]
            )
    except Exception as exc:  # noqa: BLE001 - health endpoint reports all failures
        log.warning("persistence.health_failed", error=str(exc))
        return HealthReport(
            status="unhealthy",
            ok=False,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            server_version=None,
            database=None,
            pgvector_available=False,
            **pool_snapshot,
            error=str(exc),
        )


def _snapshot_pool(pool) -> dict[str, int | None]:
    """Best-effort pool counter snapshot; returns ``None`` for missing fields."""

    def _get(name: str) -> int | None:
        value = getattr(pool, name, None)
        return value if isinstance(value, int) else None

    return {
        "pool_in_use": _get("size"),
        "pool_overflow": _get("overflow"),
        "pool_checkedout": _get("checkedout"),
    }


async def dispose_engine(engine: AsyncEngine) -> None:
    """Close the pool and release all driver resources.

    Call once at application shutdown; after this the engine is unusable.
    """

    await engine.dispose()
    log.info("persistence.engine_disposed")
