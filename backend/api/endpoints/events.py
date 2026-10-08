"""Events endpoints for the NerveCenter API.

T-H32 / D-H32: the listing is backed by the live NATS JetStream event bus
(``app.state.nats_client`` — wired by :mod:`backend.api.wiring`) instead of
hardcoded fixtures. Spec §10: events are immutable; the schema is frozen in
:mod:`schemas.events`.

Honesty contract
----------------
- Bus **not configured** (``nats_client is None``) → HTTP 200 with an empty
  list (dependency-tolerant boot, same convention as
  :func:`backend.api.endpoints._helpers.read_collection`); pagination reports
  ``total=0``.
- Bus **configured but unreachable** (client not connected, stream missing,
  or a read timeout) → HTTP 503 with an explicit error body. No fabricated
  events, no fake empty success.

All bus reads are bounded (``BUS_READ_TIMEOUT_S`` per round-trip) via
:func:`backend.events.query.list_events`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import JSONResponse

from backend.api.models import ApiResponseMeta, ListResponse
from backend.events.query import (
    BUS_READ_TIMEOUT_S,
    DEFAULT_MAX_EVENTS,
    MAX_EVENTS_LIMIT,
    EventBusError,
    find_event,
    list_events,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


def _meta(pagination: dict[str, int]) -> ApiResponseMeta:
    """Build the §46 response metadata for a list envelope."""
    return ApiResponseMeta(
        version="1.0.0",
        request_id=str(uuid4()),
        timestamp=datetime.now(UTC),
        pagination=pagination,
    )


def _bus_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """Honest 503 body: the bus was configured but a bounded read failed."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "event_bus_unavailable",
            "detail": str(exc),
            "request_id": str(uuid4()),
            "read_timeout_seconds": BUS_READ_TIMEOUT_S,
        },
    )


@router.get("/", response_model=ListResponse)
async def list_events_endpoint(
    request: Request,
    entity: str | None = Query(
        default=None,
        description="Only return events whose subject is this entity id (§46 timeline).",
    ),
    limit: int = Query(
        default=DEFAULT_MAX_EVENTS,
        ge=1,
        le=MAX_EVENTS_LIMIT,
        description="Maximum number of recent stream messages to read.",
    ),
) -> ListResponse:
    """List recent events from the NATS JetStream event bus.

    Reads the most recent messages of the configured stream via
    ``stream_info`` + bounded ``get_msg`` reads
    (:func:`backend.events.query.list_events`); returns canonical
    :class:`schemas.events.Event` records in stream order.
    """
    client = getattr(request.app.state, "nats_client", None)
    if client is None:
        # Bus not configured: dependency-tolerant empty listing (honest total=0).
        return ListResponse(data=[], meta=_meta({"total": 0, "page": 1, "per_page": 1}))

    try:
        result = await list_events(client, entity=entity, limit=limit)
    except EventBusError as exc:
        log.warning("events.listing_unavailable", error=str(exc))
        return _bus_unavailable(request, exc)

    data = [event.model_dump(mode="json") for event in result.events]
    return ListResponse(
        data=data,
        meta=_meta(
            {
                "total": result.total,
                "returned": len(data),
                "page": 1,
                "per_page": limit,
            }
        ),
    )


@router.get("/{event_id}")
async def get_event(event_id: str, request: Request) -> dict[str, Any]:
    """Get a single event by id from the event bus.

    Scans the most recent messages of the stream (bounded). Returns 404 when
    the event is not present in the scanned window — never a fabricated row.
    """
    client = getattr(request.app.state, "nats_client", None)
    if client is None:
        # No bus: nothing can be found; do not fabricate.
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        event = await find_event(client, event_id)
    except EventBusError as exc:
        log.warning("events.fetch_unavailable", event_id=event_id, error=str(exc))
        return _bus_unavailable(request, exc)

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event.model_dump(mode="json")
