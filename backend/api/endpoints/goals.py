"""Goal endpoints wired to the real GoalService.

Contract (spec §46 + MCP create_goal/update_goal):
- ``GET  /api/goals``              → list all goals
- ``POST /api/goals``              → create a new goal (201)
- ``GET  /api/goals/{goal_id}``    → get one goal
- ``POST /api/goals/{goal_id}``    → partial update (200)
- ``DELETE /api/goals/{goal_id}``  → delete (204)

When the service is not configured (local dev without NERVE_DB_URL) the
list endpoint returns an empty collection, get-by-id returns 503, and all
write endpoints return 503. This mirrors the evidence.py precedent: honest
degradation, no fabricated records, no fake 202 acceptance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from backend.api.models import (
    ApiResponseMeta,
    GoalCreateRequest,
    GoalUpdateRequest,
    ListResponse,
)
from backend.goals.service import GoalNotFoundError

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request):
    services = getattr(request.app.state, "services", {})
    service = services.get("goals") if isinstance(services, dict) else None
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Goals service not configured (NERVE_DB_URL unset).",
        )
    return service


@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_goals(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ListResponse:
    """List goals, optionally filtered by status."""
    services = getattr(request.app.state, "services", {})
    service = services.get("goals") if isinstance(services, dict) else None
    if service is None:
        return ListResponse(
            data=[],
            meta=_meta(total=0, page=1, per_page=limit),
        )
    rows = await service.list_goals(status=status, limit=limit, offset=offset)
    data = [row.model_dump(mode="json") for row in rows]
    return ListResponse(
        data=data,
        meta=_meta(total=len(data), page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.post("", status_code=201)
async def create_goal(request: Request, payload: GoalCreateRequest) -> dict[str, Any]:
    """Create a new goal and persist it through GoalService."""
    service = _service(request)
    schema = payload.model_dump(exclude_unset=True)
    # MCP contract: create_goal sends {"name": "...", "body": {...}}.
    # The "name" field maps to "title" in the Goal schema.
    if "name" in schema and "title" not in schema:
        schema["title"] = schema.pop("name")
    try:
        goal = await service.create(schema)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Goal validation failed: {exc.errors()}",
        )
    return goal.model_dump(mode="json")


@router.get("/{goal_id}")
async def get_goal(request: Request, goal_id: str) -> dict[str, Any]:
    """Get a single goal by ID."""
    service = _service(request)
    try:
        goal = await service.get(goal_id)
    except GoalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id!r} not found")
    return goal.model_dump(mode="json")


@router.post("/{goal_id}")
async def update_goal(
    request: Request, goal_id: str, payload: GoalUpdateRequest
) -> dict[str, Any]:
    """Apply a partial update to an existing goal."""
    service = _service(request)
    changes = payload.model_dump(exclude_unset=True)
    # MCP contract: update_goal may send {"name": "..."} as an alias for title.
    if "name" in changes and "title" not in changes:
        changes["title"] = changes.pop("name")
    if not changes:
        try:
            goal = await service.get(goal_id)
        except GoalNotFoundError:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id!r} not found")
        return goal.model_dump(mode="json")
    try:
        goal = await service.update(goal_id, changes)
    except GoalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id!r} not found")
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Goal validation failed: {exc.errors()}",
        )
    return goal.model_dump(mode="json")


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(request: Request, goal_id: str) -> None:
    """Delete a goal by ID."""
    service = _service(request)
    try:
        await service.delete(goal_id)
    except GoalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id!r} not found")
    return None
