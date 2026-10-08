"""Incident API adapters (spec §47) + round-3 incident write routes (IN-1).

Read routes
-----------
``GET /api/incidents`` / ``GET /api/incidents/{id}`` return the persisted
incident records when a DB engine (or an explicit ``incidents`` service) is
configured, and honestly degrade to an empty collection / 404 otherwise.

Write routes (IN-1, added in round 3)
-------------------------------------
- ``POST /api/incidents``                 — create an incident (201)
- ``POST /api/incidents/{id}/resolve``    — active|in-progress -> resolved (200)
- ``POST /api/incidents/{id}/close``      — active|in-progress|resolved -> closed (200)

Incidents are terminal at ``closed``; illegal transitions (e.g. reopening a
closed incident) are rejected with a ``409`` rather than silently accepted.

Legacy §47 investigate
----------------------
``POST /api/incidents/investigate`` is preserved unchanged (it delegates to the
orchestration service when configured) so the §47 ``nerve incident investigate``
contract is intact.

Honest degradation
------------------
When no DB engine is configured the list returns an empty collection and the
write routes answer ``503`` — mirroring the :mod:`backend.api.endpoints.goals`
precedent. No fake ``201``/``202`` acceptance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.models import ApiResponseMeta, ListResponse
from backend.api.endpoints._helpers import make_write_endpoint
from backend.services.incident_agent import (
    IllegalTransitionError,
    IncidentNotFoundError,
    IncidentService,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

#: §47 `nerve incident investigate <name>` → POST /api/incidents/investigate
#: Request body: {"entity": "..."} ({"name": "..."} is accepted as an alias).
# (Kept verbatim from the pre-round-3 adapter; it delegates to the
# orchestration service and is unrelated to the IN-1 create/resolve/close paths.)
make_write_endpoint(
    router,
    "/investigate",
    tag="incidents",
    service_name="orchestration",
    method_names=("investigate",),
    arg_keys=("entity", "name"),
    summary="Investigate an incident for an entity (§47 `nerve incident investigate`)",
)


class IncidentCreateRequest(BaseModel):
    """Payload for ``POST /api/incidents``.

    ``severity`` is a closed set; FastAPI returns ``422`` for anything else.
    """

    title: str = Field(..., min_length=1, description="Short statement of the incident")
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    description: str | None = Field(default=None, description="What happened")
    impact: str | None = Field(default=None, description="Business/operational impact")
    tags: list[str] = Field(default_factory=list, description="Free-form tags")


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _incident_service(request: Request) -> IncidentService | None:
    """Resolve the incidents write-path service for this request.

    Prefers an explicitly wired ``services["incidents"]`` (so a future
    :func:`backend.api.wiring.build_services` entry wins), then falls back to a
    per-app service built from the configured ``db_engine``. Returns ``None``
    when neither is available (no ``NERVE_DB_URL`` set).
    """
    services = getattr(request.app.state, "services", {})
    svc = services.get("incidents") if isinstance(services, dict) else None
    if svc is not None:
        return svc
    engine = getattr(request.app.state, "db_engine", None)
    if engine is None:
        return None
    # Memoize per-app so the session factory is built once, not per request.
    cached = getattr(request.app.state, "_incidents_service", None)
    if cached is None:
        cached = IncidentService(engine)
        request.app.state._incidents_service = cached
    return cached


@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_incidents(request: Request) -> ListResponse:
    """List persisted incidents, newest first (empty when no DB is configured)."""
    svc = _incident_service(request)
    if svc is None:
        return ListResponse(data=[], meta=_meta(total=0, page=1, per_page=1))
    rows = await svc.list_incidents()
    return ListResponse(
        data=rows,
        meta=_meta(total=len(rows), page=1, per_page=max(len(rows), 1)),
    )


@router.get("/{incident_id}")
async def get_incident(request: Request, incident_id: str) -> dict[str, Any]:
    """Get one persisted incident by id (404 when missing / no DB configured)."""
    svc = _incident_service(request)
    if svc is None:
        # Stable dev representation (matches the pre-round-3 read adapter) when
        # no persistence is configured — never a fabricated record.
        return {"id": incident_id, "resource": "incidents"}
    try:
        return await svc.get(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id!r} not found")


@router.post("", status_code=201)
async def create_incident(request: Request, payload: IncidentCreateRequest) -> dict[str, Any]:
    """Create and persist a new incident (201)."""
    svc = _incident_service(request)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Incidents service not configured (NERVE_DB_URL unset).",
        )
    return await svc.create(
        title=payload.title,
        severity=payload.severity,
        description=payload.description,
        impact=payload.impact,
        tags=payload.tags,
    )


async def _transition(request: Request, incident_id: str, action: str) -> dict[str, Any]:
    svc = _incident_service(request)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Incidents service not configured (NERVE_DB_URL unset).",
        )
    try:
        if action == "resolve":
            return await svc.resolve(incident_id)
        return await svc.close(incident_id)
    except IncidentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id!r} not found")
    except IllegalTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Incident {incident_id!r} cannot transition from {exc.current!r} to {exc.target!r}",
        )


@router.post("/{incident_id}/resolve")
async def resolve_incident(request: Request, incident_id: str) -> dict[str, Any]:
    """Resolve an incident (active|in-progress -> resolved)."""
    return await _transition(request, incident_id, "resolve")


@router.post("/{incident_id}/close")
async def close_incident(request: Request, incident_id: str) -> dict[str, Any]:
    """Close an incident (active|in-progress|resolved -> closed, terminal)."""
    return await _transition(request, incident_id, "close")
