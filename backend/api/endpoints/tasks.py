"""Task endpoints wired to the real TaskService.

Contract (spec §46 + MCP create_task):
- ``GET  /api/tasks``               → list all tasks
- ``POST /api/tasks``               → create a new task (201)
- ``GET  /api/tasks/{task_id}``     → get one task
- ``POST /api/tasks/{task_id}``     → partial update (200)
- ``DELETE /api/tasks/{task_id}``   → delete (204)

When the service is not configured (local dev without NERVE_DB_URL) the
list endpoint returns an empty collection, get-by-id returns 503, and all
write endpoints return 503. Honest degradation, no fake 202 acceptance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from backend.api.models import (
    ApiResponseMeta,
    ListResponse,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from backend.tasks.service import TaskNotFoundError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request):
    services = getattr(request.app.state, "services", {})
    service = services.get("tasks") if isinstance(services, dict) else None
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Tasks service not configured (NERVE_DB_URL unset).",
        )
    return service


@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_tasks(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ListResponse:
    """List tasks, optionally filtered by status."""
    services = getattr(request.app.state, "services", {})
    service = services.get("tasks") if isinstance(services, dict) else None
    if service is None:
        return ListResponse(
            data=[],
            meta=_meta(total=0, page=1, per_page=limit),
        )
    rows = await service.list_tasks(status=status, limit=limit, offset=offset)
    data = [row.model_dump(mode="json") for row in rows]
    return ListResponse(
        data=data,
        meta=_meta(total=len(data), page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.post("", status_code=201)
async def create_task(request: Request, payload: TaskCreateRequest) -> dict[str, Any]:
    """Create a new task and persist it through TaskService."""
    service = _service(request)
    schema = payload.model_dump(exclude_unset=True)
    # MCP contract: create_task sends {"name": "...", "body": {...}}.
    # The "name" field maps to "title" in the Task schema.
    if "name" in schema and "title" not in schema:
        schema["title"] = schema.pop("name")
    try:
        task = await service.create(schema)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Task validation failed: {exc.errors()}",
        )
    return task.model_dump(mode="json")


@router.get("/{task_id}")
async def get_task(request: Request, task_id: str) -> dict[str, Any]:
    """Get a single task by ID."""
    service = _service(request)
    try:
        task = await service.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return task.model_dump(mode="json")


@router.post("/{task_id}")
async def update_task(
    request: Request, task_id: str, payload: TaskUpdateRequest
) -> dict[str, Any]:
    """Apply a partial update to an existing task."""
    service = _service(request)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and "title" not in changes:
        changes["title"] = changes.pop("name")
    if not changes:
        try:
            task = await service.get(task_id)
        except TaskNotFoundError:
            raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
        return task.model_dump(mode="json")
    try:
        task = await service.update(task_id, changes)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Task validation failed: {exc.errors()}",
        )
    return task.model_dump(mode="json")


@router.delete("/{task_id}", status_code=204)
async def delete_task(request: Request, task_id: str) -> None:
    """Delete a task by ID."""
    service = _service(request)
    try:
        await service.delete(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return None
