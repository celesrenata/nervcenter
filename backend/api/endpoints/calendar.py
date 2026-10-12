"""Calendar endpoints (prompt2 Phase P2 — Calendar Integration + Conflict Reasoning).

Contract (read-only context plane, §42):
- ``GET  /api/calendar``                       → upcoming events (default 7-day horizon)
- ``POST /api/calendar/ingest``                → upsert one normalized event (201/200)
- ``GET  /api/calendar/{event_id}``           → one event
- ``DELETE /api/calendar/{event_id}``         → remove an event (sync delete)
- ``POST /api/calendar/availability``         → scheduling guard: is [start,end) free?
                                                       what blocks it? earliest it could fit?
- ``POST /api/calendar/free-time``            → earliest free slot of a duration
- ``POST /api/calendar/suggest``              → §43 reply: given a desired start +
                                                       duration, "I can do after 19:30"

The store lives in the process-wide ``get_calendar_service`` singleton (bound onto
``app.state.calendar_service`` at startup). It is *always* available — an empty
calendar returns an empty list. NerveCenter never mutates the user's real
calendar; it only holds read-only copies for availability reasoning (§42).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from backend.api.models import ApiResponseMeta, CalendarEvent, ListResponse
from backend.calendar.service import CalendarService, get_calendar_service

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _meta(total: int, per_page: int) -> ApiResponseMeta:
    return ApiResponseMeta(
        version="1.0.0",
        request_id=f"req-{uuid4().hex[:12]}",
        timestamp=datetime.now(UTC),
        pagination={"total": total, "page": 1, "per_page": per_page},
    )


def _service(request: Request) -> CalendarService:
    svc = getattr(request.app.state, "calendar_service", None)
    if svc is None:
        svc = get_calendar_service()
        request.app.state.calendar_service = svc
    return svc


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%-H:%M")


def _parse(value: str | None, field: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (``Z``-safe) or 422 — the store would
    otherwise raise and surface as a 500."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field} is not a valid ISO-8601 timestamp: {value}",
        ) from exc


def _not_found(event_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Event {event_id} not found.")


# -- request models ----------------------------------------------------------
class EventIngestRequest(BaseModel):
    """One normalized event, as posted by a calendar sync (or the user)."""

    event_id: str
    title: str
    description: str | None = None
    start: str | None = None
    end: str | None = None
    all_day: bool | None = None
    location: str | None = None
    participants: list[str] = Field(default_factory=list)
    reminder_at: str | None = None
    source: str = "calendar-sync"
    sync_id: str | None = None


class WindowRequest(BaseModel):
    start: str
    end: str


class FreeTimeRequest(BaseModel):
    start: str
    duration_minutes: int = Field(default=60, ge=1)
    horizon_minutes: int | None = Field(default=None, ge=60)


class SuggestRequest(BaseModel):
    """§43: 'Dinner tomorrow?' → 'I can do after 19:30'."""

    start: str
    duration_minutes: int = Field(default=60, ge=1)


# -- routes -----------------------------------------------------------------
@router.get("", response_model=ListResponse)
@router.get("/", response_model=ListResponse)
async def list_events(
    request: Request,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1),
) -> ListResponse:
    """Upcoming events in [start, end) — defaults to the next 7 days."""
    svc = _service(request)
    ws = _parse(start, "start")
    we = _parse(end, "end")
    events = svc.list_events(start=ws, end=we, limit=limit)
    return ListResponse(
        data=[e.model_dump(mode="json") for e in events],
        meta=_meta(total=len(events), per_page=limit),
    )


@router.post("/ingest", response_model=CalendarEvent)
async def ingest_event(
    request: Request, payload: EventIngestRequest, response: Response
) -> CalendarEvent:
    """Upsert one event by id (idempotent sync replay → 200; new → 201)."""
    svc = _service(request)
    p = payload.model_dump()
    # Validate timestamps up front so a malformed date is a 422, not a 500.
    for field in ("start", "end", "reminder_at"):
        raw = p.get(field)
        parsed = _parse(raw, field)
        p[field] = parsed.isoformat() if parsed is not None else None
    is_new = svc.get_event(payload.event_id) is None
    event = svc.ingest(p)
    response.status_code = 201 if is_new else 200
    return event


@router.post("/availability", response_model=dict)
async def availability(request: Request, payload: WindowRequest) -> dict[str, Any]:
    """Scheduling guard (§42): does this window conflict, and when is it free?"""
    svc = _service(request)
    start = _parse(payload.start, "start")
    end = _parse(payload.end, "end")
    assert start is not None and end is not None
    result = svc.availability(start, end)
    return {
        "available": result["available"],
        "start": _iso(result["start"]),
        "end": _iso(result["end"]),
        "conflicts": [c.model_dump(mode="json") for c in result["conflicts"]],
        "earliest_free_after": _iso(result["earliest_free_after"]),
    }


@router.post("/free-time", response_model=dict)
async def free_time(request: Request, payload: FreeTimeRequest) -> dict[str, Any]:
    """Earliest start in the horizon where a slot of the given duration fits."""
    svc = _service(request)
    start = _parse(payload.start, "start")
    assert start is not None
    duration = timedelta(minutes=payload.duration_minutes)
    horizon = (
        timedelta(minutes=payload.horizon_minutes)
        if payload.horizon_minutes
        else None
    )
    slot = svc.free_slot(start, duration, horizon=horizon)
    return {
        "start": _iso(start),
        "duration_minutes": payload.duration_minutes,
        "free_at": _iso(slot),
        "found": slot is not None,
    }


@router.post("/suggest", response_model=dict)
async def suggest(request: Request, payload: SuggestRequest) -> dict[str, Any]:
    """§43 conflict-reasoning reply: 'Dinner tomorrow?' → 'after 19:30'."""
    svc = _service(request)
    start = _parse(payload.start, "start")
    assert start is not None
    duration = timedelta(minutes=payload.duration_minutes)
    window = svc.availability(start, start + duration)
    if window["available"]:
        return {
            "available": True,
            "start": _iso(start),
            "earliest_free_after": _iso(start),
            "suggested_at": _iso(start),
            "suggestion": f"Yes — {start:%A %H:%M} works.",
            "conflicts": [],
        }
    earliest = window["earliest_free_after"]
    if earliest.date() == start.date():
        suggestion = f"I can do after {_fmt_time(earliest)}."
    else:
        suggestion = f"I can do after {earliest:%A} {_fmt_time(earliest)}."
    return {
        "available": False,
        "start": _iso(start),
        "earliest_free_after": _iso(earliest),
        "suggested_at": _iso(earliest),
        "suggestion": suggestion,
        "conflicts": [c.model_dump(mode="json") for c in window["conflicts"]],
    }


@router.get("/{event_id}", response_model=CalendarEvent)
async def get_event(request: Request, event_id: str) -> CalendarEvent:
    svc = _service(request)
    ev = svc.get_event(event_id)
    if ev is None:
        raise _not_found(event_id)
    return ev


@router.delete("/{event_id}", status_code=204)
async def delete_event(request: Request, event_id: str) -> None:
    svc = _service(request)
    if not svc.delete(event_id):
        raise _not_found(event_id)
    return None
