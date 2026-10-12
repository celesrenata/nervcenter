"""Calendar plane — service (prompt2 Phase P2: Calendar Integration + Conflict Reasoning).

The calendar is **read-only context** for the rest of NerveCenter
(prompt2 §42): it answers *availability* questions — "when am I free?",
"does this conflict?", "what's the next opening?" — so that messages
("Dinner tomorrow?" → "I can do after 7:30", §43), scheduling, deadlines,
meeting prep and follow-up timing can all reason about the user's schedule.

NerveCenter does not own the calendar: events are either read-only synced
copies from a provider (Apple/Google/Microsoft/CalDAV, §42) or ingested as
normalized entries via ``POST /api/calendar/ingest``. The store here is the
process-wide, in-process singleton (same convention as the P0 attention and
P1 messages planes). Everything below is deterministic and clock-injected so
the conflict logic is unit-testable without a real calendar.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from backend.api.models import CalendarEvent
from backend.attention.service import _now  # reuse the same UTC-now helper

#: How many hours a *desired* window may extend into the future when
#: computing availability (the "search horizon" for free slots).
DEFAULT_HORIZON = timedelta(days=7)

#: Minimum gap between the end of one event and the start of a candidate
#: slot — keeps suggestions realistic (a little breathing room).
BUFFER = timedelta(minutes=0)


def _ensure_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_span(ev: CalendarEvent) -> tuple[datetime, datetime]:
    """Return the (start, end) span an event blocks, UTC-normalized.

    All-day events block the whole calendar day (00:00 → 24:00 UTC); timed
    events use their start/end (end defaults to start for zero-duration
    points).
    """
    if ev.all_day or ev.start is None:
        day = (ev.start or _now()).date()
        start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        return start, start + timedelta(days=1)
    start = ev.start
    end = ev.end or ev.start
    if end <= start:
        end = start
    return start, end


class CalendarService:
    """In-process calendar store + availability / conflict reasoning."""

    def __init__(self) -> None:
        self._events: dict[str, CalendarEvent] = {}

    # -- mutation ----------------------------------------------------------
    def ingest(self, payload: dict[str, Any]) -> CalendarEvent:
        """Upsert one event by ``event_id`` (idempotent for sync replays)."""
        event_id = payload["event_id"]
        data = dict(payload)
        data["start"] = _ensure_utc(data.get("start"))
        data["end"] = _ensure_utc(data.get("end"))
        if data.get("reminder_at") is not None:
            data["reminder_at"] = _ensure_utc(data["reminder_at"])
        if data.get("all_day") is None:
            data["all_day"] = data.get("start") is None
        event = CalendarEvent(**data)
        if event.created_at is None:
            event.created_at = _now()
        event.updated_at = _now()
        self._events[event_id] = event
        return event

    def delete(self, event_id: str) -> bool:
        return self._events.pop(event_id, None) is not None

    # -- read --------------------------------------------------------------
    def list_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 200,
    ) -> list[CalendarEvent]:
        """Events in [start, end) (default: from now to the horizon)."""
        ws = _ensure_utc(start) or _now()
        we = _ensure_utc(end) or (ws + DEFAULT_HORIZON)
        out = [
            ev
            for ev in self._events.values()
            if _event_span(ev)[0] < we and _event_span(ev)[1] > ws
        ]
        return sorted(out, key=lambda e: _event_span(e)[0])[:limit]

    def get_event(self, event_id: str) -> CalendarEvent | None:
        return self._events.get(event_id)

    # -- conflict / availability reasoning (§42/§43) -----------------------
    def conflicts(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Events overlapping the proposed [start, end) window."""
        ws = _ensure_utc(start)
        we = _ensure_utc(end)
        assert ws is not None and we is not None
        out = []
        for ev in self._events.values():
            es, ee = _event_span(ev)
            if es < we and ee > ws:
                out.append(ev)
        return sorted(out, key=lambda e: _event_span(e)[0])

    def availability(self, start: datetime, end: datetime) -> dict[str, Any]:
        """Scheduling guard: is [start, end) free, and what blocks it?

        Returns ``available`` (bool), the ``conflicts`` list, and
        ``earliest_free_after`` — the first moment at/after ``start`` from
        which the window would fit if nothing blocks it (used to propose
        "after 7:30" style answers, §43).
        """
        ws = _ensure_utc(start)
        we = _ensure_utc(end)
        assert ws is not None and we is not None
        clashes = self.conflicts(ws, we)
        if not clashes:
            return {
                "available": True,
                "start": ws,
                "end": we,
                "conflicts": [],
                "earliest_free_after": ws,
            }
        # Earliest time the whole window could fit: after the last-conflicting
        # event ends, then step past each subsequent clash iteratively.
        candidate = max(_event_span(c)[1] for c in clashes)
        for _ in range(64):  # bounded fixed-point; deterministic
            if not self.conflicts(candidate, candidate + (we - ws)):
                break
            candidate = max(
                _event_span(c)[1]
                for c in self.conflicts(candidate, candidate + (we - ws))
            )
        return {
            "available": False,
            "start": ws,
            "end": we,
            "conflicts": clashes,
            "earliest_free_after": candidate + BUFFER,
        }

    def free_slot(
        self,
        start: datetime,
        duration: timedelta,
        horizon: timedelta | None = None,
    ) -> datetime | None:
        """Earliest start time in [start, start+horizon] where a slot of
        ``duration`` fits without conflict; ``None`` if the horizon fills up."""
        ws = _ensure_utc(start)
        assert ws is not None
        step = timedelta(minutes=30)
        horizon = horizon or DEFAULT_HORIZON
        candidate = ws
        limit = ws + horizon
        while candidate + duration <= limit:
            if not self.conflicts(candidate, candidate + duration):
                return candidate
            # Jump to just after the next clash ends (deterministic fast-forward).
            clash_end = max(
                (_event_span(c)[1] for c in self.conflicts(candidate, candidate + duration)),
                default=candidate + step,
            )
            nxt = max(candidate + step, clash_end)
            if nxt <= candidate:  # no forward progress (degenerate overlap)
                candidate = candidate + step
            else:
                candidate = nxt
        return None

    def next_free_after(self, start: datetime, duration: timedelta) -> datetime | None:
        """Convenience alias used by the "when can we meet?" reply path."""
        return self.free_slot(start, duration)

    # -- dev ----------------------------------------------------------------
    def seed_demo(self) -> None:
        """Pre-populate a demo schedule so /calendar has content (dev only)."""
        day = _now() + timedelta(days=1)
        base = datetime(day.year, day.month, day.day, 18, 0, tzinfo=UTC)
        self.ingest({
            "event_id": "demo-1",
            "title": "Dinner with family",
            "start": base.isoformat(),
            "end": (base + timedelta(hours=1)).isoformat(),
            "location": "Home",
            "source": "calendar-sync",
        })
        self.ingest({
            "event_id": "demo-2",
            "title": "Design review",
            "start": (base - timedelta(hours=2)).isoformat(),
            "end": (base - timedelta(hours=1)).isoformat(),
            "source": "calendar-sync",
        })


# -- process-wide singleton (mirrors the P1 messages plane) -----------------
_calendar_service: CalendarService | None = None


def get_calendar_service() -> CalendarService:
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service


def reset_calendar_service() -> None:
    global _calendar_service
    _calendar_service = None


def _request_id() -> str:
    return f"req-{uuid4().hex[:12]}"
