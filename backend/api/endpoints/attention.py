"""Attention endpoints (prompt2 Phase P0 — Personal Operations Plane).

Contract:
- ``GET  /api/attention``                     → ranked list (optionally by state)
- ``GET  /api/attention/now``                 → the Now screen's feed (NOW bucket)
- ``POST /api/attention``                     → create an item (201); scorer fills
                                               ``priority`` + ``why`` deterministically
- ``GET  /api/attention/{attention_id}``      → one item
- ``POST /api/attention/{attention_id}/resolve``   → RESOLVED
- ``POST /api/attention/{attention_id}/suppress``  → SUPPRESSED
- ``POST /api/attention/{attention_id}/acknowledge`` → resolve (handled)
- ``POST /api/attention/{attention_id}/snooze``    → defer to a later window

The queue lives in the process-wide :func:`backend.attention.get_attention_service`
singleton (bound onto ``app.state.attention_service`` at startup). Unlike the
engine-backed services it is *always* available, so these routes never 503 for
"service not configured" — an empty queue returns an empty list. Scoring is
deterministic and explainable (prompt2 §21/§22); there is no opaque ranking.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.api.models import (
    ApiResponseMeta,
    AttentionItem,
    AttentionState,
    ListResponse,
)
from backend.attention.service import AttentionService, get_attention_service

router = APIRouter(prefix="/api/attention", tags=["attention"])


def _meta(**pagination: int | None) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={k: v for k, v in pagination.items() if v is not None} or None,
    )


def _service(request: Request) -> AttentionService:
    svc = getattr(request.app.state, "attention_service", None)
    if svc is None:
        # Defensive: the singleton is always resolvable even if startup wiring
        # has not run yet (e.g. unit tests hitting the router directly).
        svc = get_attention_service()
        request.app.state.attention_service = svc
    return svc


def _dump(item: AttentionItem) -> dict[str, Any]:
    return item.model_dump(mode="json")


def _not_found(attention_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Attention item {attention_id} not found.")


class AttentionCreateRequest(BaseModel):
    """Request body for creating an AttentionItem.

    ``urgency``/``importance``/``due`` are optional inputs to the deterministic
    scorer; when omitted the scorer still produces a defensible priority and a
    human-readable ``why`` explanation.
    """

    reason: str
    priority: float | None = Field(default=None, ge=0.0, le=1.0)
    urgency: float | None = Field(default=None, ge=0.0, le=1.0)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    due: datetime | None = None
    entities: list[str] = []
    sources: list[str] = []
    suggested_action: str | None = None
    status: AttentionState = AttentionState.NOW
    why: list[str] = []


class AttentionSnoozeRequest(BaseModel):
    until: datetime | None = None


@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_attention(
    request: Request,
    status: AttentionState | None = Query(default=None),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ListResponse:
    """List attention items, ranked by priority, optionally filtered by state."""
    svc = _service(request)
    items = svc.list(status=status)
    total = len(items)
    page_items = items[offset : offset + limit]
    return ListResponse(
        data=[_dump(i) for i in page_items],
        meta=_meta(total=total, page=offset // max(limit, 1) + 1, per_page=limit),
    )


@router.get("/now", response_model=ListResponse)
async def now_attention(request: Request, limit: int = Query(default=10, ge=1)) -> ListResponse:
    """The Now screen's feed: the top-ranked NOW-bucket items only (§26)."""
    svc = _service(request)
    items = svc.now()[:limit]
    return ListResponse(
        data=[_dump(i) for i in items],
        meta=_meta(total=len(svc.now()), per_page=limit),
    )


@router.get("/{attention_id}", response_model=AttentionItem)
async def get_attention(request: Request, attention_id: str) -> AttentionItem:
    item = _service(request).get(attention_id)
    if item is None:
        raise _not_found(attention_id)
    return item


@router.post("", status_code=201, response_model=AttentionItem)
async def create_attention(request: Request, payload: AttentionCreateRequest) -> AttentionItem:
    """Create an item; the deterministic scorer fills priority + why (§21/§22)."""
    svc = _service(request)
    data = payload.model_dump(exclude_unset=True)
    item = svc.create(data)
    return item


def _mutate(request: Request, attention_id: str, fn) -> AttentionItem:
    svc = _service(request)
    result = fn(svc, attention_id)
    if result is None:
        raise _not_found(attention_id)
    return result


@router.post("/{attention_id}/resolve", response_model=AttentionItem)
async def resolve_attention(request: Request, attention_id: str) -> AttentionItem:
    return _mutate(request, attention_id, lambda s, i: s.resolve(i))


@router.post("/{attention_id}/suppress", response_model=AttentionItem)
async def suppress_attention(request: Request, attention_id: str) -> AttentionItem:
    return _mutate(request, attention_id, lambda s, i: s.suppress(i))


@router.post("/{attention_id}/acknowledge", response_model=AttentionItem)
async def acknowledge_attention(request: Request, attention_id: str) -> AttentionItem:
    return _mutate(request, attention_id, lambda s, i: s.acknowledge(i))


@router.post("/{attention_id}/snooze", response_model=AttentionItem)
async def snooze_attention(
    request: Request, attention_id: str, payload: AttentionSnoozeRequest
) -> AttentionItem:
    return _mutate(request, attention_id, lambda s, i: s.snooze(i, payload.until))
