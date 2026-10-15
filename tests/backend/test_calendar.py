"""Prompt2 Phase P2 — Calendar plane tests (availability + conflict reasoning).

Covers (prompt2 §42/§43):
- ``CalendarEvent`` schema (timed + all-day).
- Ingest/upsert: idempotent sync replay (200 on replay), 201 on new.
- Conflict detection: overlapping events block a proposed window; adjacent
  (touching) events do NOT conflict.
- The scheduling guard: ``POST /availability`` reports free vs. blocked with
  the earliest free-after moment.
- Free-slot search: ``POST /free-time`` finds the earliest gap of a given
  duration; reports honestly when the horizon fills up.
- §43 suggestion: ``POST /suggest`` produces the "I can do after 7:30" reply
  when a window is blocked, and confirms the original time when free.
- Honest 404s for unknown events.

The calendar service is an in-process singleton, so tests get a fresh app per
test via :func:`backend.api.app.create_app` and fresh singletons via the reset
hooks — no database or NATS required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.models import CalendarEvent
from backend.calendar import CalendarService, reset_calendar_service


def _day() -> datetime:
    """A fixed reference day (deterministic conflict math)."""
    return datetime(2026, 10, 14, tzinfo=UTC)


def at(hours: float, minutes: int = 0) -> datetime:
    """Reference day + hours (fractional ok) + minutes → a datetime on it."""
    return _day() + timedelta(hours=hours, minutes=minutes)


@pytest.fixture
def client():
    reset_calendar_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_calendar_service()


def _ev(event_id: str, title: str, start: datetime, end: datetime, **over) -> dict:
    payload = {
        "event_id": event_id,
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    payload.update(over)
    return payload


def _ingest(client: TestClient, payload: dict, status: int) -> None:
    res = client.post("/api/calendar/ingest", json=payload)
    assert res.status_code == status, res.text


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_event_defaults():
    ev = CalendarEvent(event_id="e1", title="Standup")
    assert ev.source == "calendar-sync"
    assert ev.all_day is False
    assert ev.participants == []


def test_all_day_event():
    ev = CalendarEvent(event_id="e2", title="Holiday", all_day=True, start=_day())
    assert ev.all_day is True
    assert ev.end is None


# ---------------------------------------------------------------------------
# Ingest / upsert
# ---------------------------------------------------------------------------


def test_ingest_new_is_201_replay_is_200(client):
    payload = _ev("e1", "Design review", at(9), at(10))
    _ingest(client, payload, 201)
    _ingest(client, payload, 200)
    # NOTE: explicit [start, end) window — list_events() defaults its window to
    # [now, now+7d) anchored at the real clock, so a fixed-date fixture read via
    # the default window is a time-bomb (silently fails the day the reference
    # date passes). The event sits at at(9)-at(10) on the reference day.
    data = client.get(
        "/api/calendar",
        params={"start": at(0).isoformat(), "end": at(24).isoformat()},
    ).json()["data"]
    assert len(data) == 1


def test_ingest_invalid_window_422(client):
    res = client.post(
        "/api/calendar/ingest",
        json={"event_id": "bad", "title": "x", "start": "not-a-date"},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Conflict detection (§42 availability)
# ---------------------------------------------------------------------------


def test_availability_free_window(client):
    res = client.post(
        "/api/calendar/availability",
        json={"start": at(9).isoformat(), "end": at(10).isoformat()},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["conflicts"] == []
    assert body["earliest_free_after"] == body["start"]


def test_availability_blocked_by_overlap(client):
    # 18:00–19:00 event blocks the "dinner tomorrow?" window.
    _ingest(client, _ev("e-dinner", "18:00 appointment", at(18), at(19)), 201)
    body = client.post(
        "/api/calendar/availability",
        json={"start": at(18).isoformat(), "end": at(19).isoformat()},
    ).json()
    assert body["available"] is False
    assert [c["event_id"] for c in body["conflicts"]] == ["e-dinner"]
    assert body["earliest_free_after"] == at(19).isoformat()


def test_availability_partial_overlap_blocks(client):
    # 09:00–10:00 event; asking for 09:30–10:30 overlaps → blocked, and the
    # whole window shifts to 10:00.
    _ingest(client, _ev("e1", "Review", at(9), at(10)), 201)
    body = client.post(
        "/api/calendar/availability",
        json={"start": at(9, 30).isoformat(), "end": at(10, 30).isoformat()},
    ).json()
    assert body["available"] is False
    assert body["earliest_free_after"] == at(10).isoformat()


def test_adjacent_events_do_not_conflict(client):
    _ingest(client, _ev("e1", "A", at(9), at(10)), 201)
    body = client.post(
        "/api/calendar/availability",
        json={"start": at(10).isoformat(), "end": at(11).isoformat()},
    ).json()
    assert body["available"] is True


def test_all_day_event_blocks_a_full_day(client):
    _ingest(
        client,
        {"event_id": "e-hol", "title": "Holiday", "all_day": True, "start": _day().isoformat()},
        201,
    )
    body = client.post(
        "/api/calendar/availability",
        json={"start": at(14).isoformat(), "end": at(15).isoformat()},
    ).json()
    assert body["available"] is False
    assert [c["event_id"] for c in body["conflicts"]] == ["e-hol"]
    assert body["earliest_free_after"] == at(24).isoformat()


# ---------------------------------------------------------------------------
# Free-slot search
# ---------------------------------------------------------------------------


def test_free_slot_finds_earliest_gap(client):
    # Busy 09:00–11:00; a 60-min slot searched from 09:00 should land at 11:00.
    _ingest(client, _ev("e1", "Busy", at(9), at(11)), 201)
    body = client.post(
        "/api/calendar/free-time",
        json={"start": at(9).isoformat(), "duration_minutes": 60},
    ).json()
    assert body["found"] is True
    assert body["free_at"] == at(11).isoformat()


def test_free_slot_none_when_horizon_full(client):
    # A wall of back-to-back 2-hour events across the whole horizon → no fit.
    start = at(9)
    for i in range(200):
        _ingest(
            client,
            _ev(f"e{i}", "Busy", start + timedelta(hours=2 * i), start + timedelta(hours=2 * i + 2)),
            201,
        )
    body = client.post(
        "/api/calendar/free-time",
        json={"start": start.isoformat(), "duration_minutes": 60, "horizon_minutes": 3 * 60},
    ).json()
    assert body["found"] is False
    assert body["free_at"] is None


def test_free_slot_none_when_calendar_empty_returns_start(client):
    body = client.post(
        "/api/calendar/free-time",
        json={"start": at(10).isoformat(), "duration_minutes": 30},
    ).json()
    assert body["found"] is True
    assert body["free_at"] == body["start"]


# ---------------------------------------------------------------------------
# §43 conflict-reasoning reply
# ---------------------------------------------------------------------------


def test_suggest_blocks_and_proposes_after(client):
    _ingest(client, _ev("e-dinner", "Dinner with family", at(18), at(19)), 201)
    body = client.post(
        "/api/calendar/suggest",
        json={"start": at(18).isoformat(), "duration_minutes": 60},
    ).json()
    assert body["available"] is False
    assert body["suggested_at"] == at(19).isoformat()
    assert body["suggestion"] == "I can do after 19:00."
    assert [c["event_id"] for c in body["conflicts"]] == ["e-dinner"]


def test_suggest_confirms_free_time(client):
    body = client.post(
        "/api/calendar/suggest",
        json={"start": at(18).isoformat(), "duration_minutes": 60},
    ).json()
    assert body["available"] is True
    assert "works" in body["suggestion"]


def test_suggest_late_conflict_same_day(client):
    _ingest(client, _ev("e-late", "Late thing", at(23), at(23.5)), 201)
    body = client.post(
        "/api/calendar/suggest",
        json={"start": at(23).isoformat(), "duration_minutes": 60},
    ).json()
    assert body["available"] is False
    assert body["suggested_at"] == at(23.5).isoformat()
    assert body["suggestion"] == "I can do after 23:30."


# ---------------------------------------------------------------------------
# Get / delete — honest 404s
# ---------------------------------------------------------------------------


def test_get_event_roundtrip(client):
    payload = _ev("e-get", "One-on-one", at(15), at(16), location="Room 4")
    _ingest(client, payload, 201)
    res = client.get("/api/calendar/e-get")
    assert res.status_code == 200
    ev = res.json()
    assert ev["event_id"] == "e-get"
    assert ev["title"] == "One-on-one"
    assert ev["location"] == "Room 4"
    assert ev["source"] == "calendar-sync"


def test_get_unknown_event_404(client):
    assert client.get("/api/calendar/e-nope").status_code == 404
    assert client.delete("/api/calendar/e-nope").status_code == 404


def test_delete_then_404(client):
    _ingest(client, _ev("e-del", "Temp", at(12), at(13)), 201)
    assert client.delete("/api/calendar/e-del").status_code == 204
    assert client.get("/api/calendar/e-del").status_code == 404


def test_list_filters_to_window(client):
    _ingest(client, _ev("e1", "A", at(9), at(10)), 201)
    _ingest(client, _ev("e2", "B", at(25), at(26)), 201)
    # NOTE: explicit [start, end) window — the default list window is
    # [now, now+7d) anchored at the real clock, so reading both fixed-date
    # fixtures (e1 at day-1 at(9), e2 at day-2 at(25)) through the default
    # window is a time-bomb. Cover both with at(0)..at(30).
    data = client.get(
        "/api/calendar",
        params={"start": at(0).isoformat(), "end": at(30).isoformat()},
    ).json()["data"]
    assert {e["event_id"] for e in data} == {"e1", "e2"}
    narrow = client.get(
        "/api/calendar",
        params={"start": at(8).isoformat(), "end": at(11).isoformat()},
    ).json()["data"]
    assert [e["event_id"] for e in narrow] == ["e1"]


def test_service_reset_hook():
    # NOTE: pass an explicit [start, end) window AND give the ingested event a
    # real duration, strictly inside the window. list_events() defaults its
    # window to [now, now + 7d), and _day() is a hardcoded reference day
    # (2026-10-14) that is *in the past* relative to the real clock from that
    # date onward — relying on the default made this test a time-bomb (it
    # silently started failing the day the reference date passed). A zero-
    # duration event sitting exactly on the window boundary is also excluded
    # by the half-open overlap check (ev_span[1] > ws), so the event must
    # actually span into the window. This keeps the assertion clock-invariant
    # while still proving reset_calendar_service() drops the old instance and
    # a fresh one is empty.
    svc = CalendarService()
    svc.ingest(
        {
            "event_id": "m-reset",
            "title": "x",
            "start": at(9).isoformat(),
            "end": at(10).isoformat(),
        }
    )
    assert len(svc.list_events(start=at(8).isoformat(), end=at(11).isoformat())) == 1
    reset_calendar_service()
    fresh = CalendarService()
    assert fresh is not svc
    assert len(fresh.list_events(start=at(8).isoformat(), end=at(11).isoformat())) == 0
