"""Kubernetes and load-balancer health endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


async def _database_check(request: Request) -> dict[str, Any]:
    """Run the configured database probe without failing the HTTP request."""
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return {"status": "unreachable", "message": "database is not configured"}
    try:
        from backend.persistence.connection import check_health

        report = await check_health(engine)
        result = report.as_dict()
        result["status"] = "ok" if report.ok else "unreachable"
        return result
    except Exception as exc:  # noqa: BLE001 - health must degrade gracefully
        return {"status": "unreachable", "message": str(exc)}


async def _nats_check(request: Request) -> dict[str, Any]:
    """Run the configured NATS probe without failing the HTTP request."""
    client = getattr(request.app.state, "nats_client", None)
    if client is None:
        return {"status": "unreachable", "message": "NATS is not configured"}
    try:
        report = await client.health_check()
        return {
            **report,
            "status": "ok" if report.get("connected") else "unreachable",
        }
    except Exception as exc:  # noqa: BLE001 - health must degrade gracefully
        return {"status": "unreachable", "message": str(exc)}


async def _health(request: Request) -> dict[str, Any]:
    db, nats = await _database_check(request), await _nats_check(request)
    checks = {"db": db, "nats": nats}
    healthy = all(check.get("status") == "ok" for check in checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "version": request.app.version,
        "checks": checks,
    }


@router.get("/api/health")
async def api_health(request: Request) -> dict[str, Any]:
    """Return a dependency-tolerant health report for Kubernetes probes."""
    return await _health(request)


@router.get("/api/v1/health")
async def versioned_api_health(request: Request) -> dict[str, Any]:
    """Compatibility alias for clients using the versioned API prefix."""
    return await _health(request)
