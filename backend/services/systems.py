"""Live system-status service (web ``/api/systems`` contract, spec §49).

The web Systems view renders a list of ``SystemStatus`` rows of the shape
``{name, status, version, message, checkedAt}`` where ``status`` is one of
``healthy | unhealthy | degraded | unknown``.

This service composes those rows from *real* dependency probes instead of
hardcoded fixtures:

- ``nervecenter-api`` — always reported, carrying the API version; ``healthy``
  while the process is serving (it is, by definition, answering the request).
- ``postgres`` — probed via ``backend.persistence.connection.check_health``
  against the configured DB engine. A healthy probe maps to ``healthy``; a
  degraded (no pgvector) probe to ``degraded``; a failed probe to ``unhealthy``.
- ``nats`` — probed via ``NatsClient.health_check()`` (a real, bounded probe);
  ``connected: true`` maps to ``healthy``, otherwise ``unhealthy``.

When a dependency is not configured the corresponding row is omitted entirely
(the view degrades to showing only the configured systems) rather than emitting
a fabricated status. Every probe is bounded so the endpoint never hangs on an
unreachable dependency.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger(__name__)

#: Per-probe timeout (seconds). Kept small so ``GET /api/systems`` stays snappy
#: even when the database or NATS are slow or unreachable.
PROBE_TIMEOUT_S = 3.0

#: API service version reported on the ``nervecenter-api`` row.
API_VERSION = "0.1.0"


class SystemsService:
    """Composes live system-status rows from the configured dependencies.

    Parameters
    ----------
    db_engine:
        The async SQLAlchemy engine (``app.state.db_engine``) or ``None`` when no
        database URL is configured.
    nats_client:
        The NATS client (``app.state.nats_client``) or ``None`` when no NATS URL
        is configured.
    """

    def __init__(self, db_engine: Any, nats_client: Any) -> None:
        self._engine = db_engine
        self._nats = nats_client

    async def list_systems(self) -> list[dict[str, Any]]:
        """Return the current system-status rows.

        Rows are returned newest-probed last; ordering is stable:
        ``nervecenter-api``, ``postgres`` (when configured), ``nats`` (when
        configured).
        """
        rows: list[dict[str, Any]] = [
            {
                "name": "nervecenter-api",
                "status": "healthy",
                "version": API_VERSION,
                "message": "API service is up and answering requests",
                "checked_at": datetime.now(UTC).isoformat(),
            }
        ]
        db_row = await self._db_row()
        if db_row is not None:
            rows.append(db_row)
        nats_row = await self._nats_row()
        if nats_row is not None:
            rows.append(nats_row)
        return rows

    async def _db_row(self) -> dict[str, Any] | None:
        if self._engine is None:
            return None
        from backend.persistence.connection import check_health

        try:
            report = await asyncio.wait_for(check_health(self._engine), timeout=PROBE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - probe failure must not break the endpoint
            log.warning("systems.db_probe_failed", error=str(exc))
            return {
                "name": "postgres",
                "status": "unhealthy",
                "version": None,
                "message": f"database probe failed: {exc}",
                "checked_at": datetime.now(UTC).isoformat(),
            }
        status = "healthy" if report.ok else ("degraded" if report.status == "degraded" else "unhealthy")
        detail = report.as_dict()
        return {
            "name": "postgres",
            "status": status,
            "version": detail.get("server_version"),
            "message": self._db_message(detail),
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def _nats_row(self) -> dict[str, Any] | None:
        if self._nats is None:
            return None
        try:
            report = await asyncio.wait_for(self._nats.health_check(), timeout=PROBE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - probe failure must not break the endpoint
            log.warning("systems.nats_probe_failed", error=str(exc))
            return {
                "name": "nats",
                "status": "unhealthy",
                "version": None,
                "message": f"NATS probe failed: {exc}",
                "checked_at": datetime.now(UTC).isoformat(),
            }
        connected = bool(report.get("connected"))
        server = report.get("server_info") or {}
        version = server.get("version") if isinstance(server, dict) else None
        message = "JetStream event bus is connected" if connected else "NATS is configured but not connected"
        if not connected and report.get("error"):
            message = f"NATS not connected: {report.get('error')}"
        return {
            "name": "nats",
            "status": "healthy" if connected else "unhealthy",
            "version": version,
            "message": message,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _db_message(detail: dict[str, Any]) -> str:
        version = detail.get("server_version")
        base = f"PostgreSQL {version}" if version else "PostgreSQL"
        if detail.get("pgvector_available"):
            base += " · pgvector available"
        if detail.get("error"):
            base += f" · {detail.get('error')}"
        return base
