"""Entity endpoints wired to the real EntityService.

Contract (spec §46 + MCP get_entity/create_entity):
- ``GET  /api/entities``               → list all entities
- ``POST /api/entities``               → create a new entity (201)
- ``GET  /api/entities/{entity_id}``   → get one entity
- ``POST /api/entities/{entity_id}``   → partial update (200)
- ``DELETE /api/entities/{entity_id}`` → delete (204)

When the service is not configured (local dev without NERVE_DB_URL) the
list endpoint returns an empty collection, get-by-id returns 503, and all
write endpoints return 503. Honest degradation, no fabricated records,
no fake 202 acceptance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from backend.api.models import (
    ApiResponseMeta,
    EntityCreateRequest,
    EntityUpdateRequest,
    ListResponse,
)
from backend.knowledge.entity import EntityConflictError, EntityNotFoundError

router = APIRouter(prefix="/api/entities", tags=["entities"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request):
    services = getattr(request.app.state, "services", {})
    service = services.get("entities") if isinstance(services, dict) else None
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Entities service not configured (NERVE_DB_URL unset).",
        )
    return service


@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_entities(
    request: Request,
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ListResponse:
    """List entities, optionally filtered by type."""
    services = getattr(request.app.state, "services", {})
    service = services.get("entities") if isinstance(services, dict) else None
    if service is None:
        return ListResponse(
            data=[],
            meta=_meta(total=0, page=1, per_page=limit),
        )
    rows = await service.list_entities(entity_type=entity_type, limit=limit, offset=offset)
    data = [row.model_dump(mode="json") for row in rows]
    return ListResponse(
        data=data,
        meta=_meta(total=len(data), page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.post("", status_code=201)
async def create_entity(
    request: Request, payload: EntityCreateRequest
) -> dict[str, Any]:
    """Create a new entity and persist it through EntityService."""
    service = _service(request)
    schema = payload.model_dump(exclude_unset=True)
    # The Entity schema carries a nested TemporalWindow ``valid`` object, not
    # flat ``valid_from``/``valid_to`` keys; map the flat request fields onto it.
    schema.pop("valid_from", None)
    schema.pop("valid_to", None)
    if payload.valid_from is not None or payload.valid_to is not None:
        schema["valid"] = {
            "valid_from": payload.valid_from,
            "valid_to": payload.valid_to,
        }
    try:
        entity = await service.create(schema)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Entity validation failed: {exc.errors()}",
        )
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return entity.model_dump(mode="json")


@router.get("/{entity_id}")
async def get_entity(request: Request, entity_id: str) -> dict[str, Any]:
    """Get a single entity by ID."""
    service = _service(request)
    try:
        entity = await service.get(entity_id)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")
    return entity.model_dump(mode="json")


@router.post("/{entity_id}")
async def update_entity(
    request: Request, entity_id: str, payload: EntityUpdateRequest
) -> dict[str, Any]:
    """Apply a partial update to an existing entity."""
    service = _service(request)
    changes = payload.model_dump(exclude_unset=True)
    schema = payload.model_dump(exclude_unset=True)
    schema.pop("valid_from", None)
    schema.pop("valid_to", None)
    if payload.valid_from is not None or payload.valid_to is not None:
        schema["valid"] = {
            "valid_from": payload.valid_from,
            "valid_to": payload.valid_to,
        }
    if not schema:
        try:
            entity = await service.get(entity_id)
        except EntityNotFoundError:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")
        return entity.model_dump(mode="json")
    try:
        entity = await service.update(entity_id, schema)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Entity validation failed: {exc.errors()}",
        )
    return entity.model_dump(mode="json")


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(request: Request, entity_id: str) -> None:
    """Delete an entity by ID."""
    service = _service(request)
    try:
        await service.delete(entity_id)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id!r} not found")
    return None
