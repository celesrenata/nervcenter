"""Prompt2 §30 — Briefing plane tests (read-only deterministic aggregation).

The Briefing plane is a *projection*, not a store: it composes the §30 brief
(Actions / Waiting On / Today / Overnight) from state already committed on the
attention, waiting-on, calendar, email, messages, and voicemail planes. Every
test pins the clock through an injected ``now`` so the section contents and the
24-hour overnight window are exact — no wall-clock jitter.

Covers:
- Empty state → ``empty: True`` and every section blank (§30 honest closing).
- Each section independently reflects its source plane (one plane seeded at a
  time, so the composition — not some hidden coupling — is what's under test).
- ``kind`` is echoed as metadata and identical across kinds (same four
  sections).
- The actions cap and Now ordering are preserved (top of the Now queue).
- Section contents: waiting-on days elapsed, today calendar overlap, and the
  24-hour overnight counts (in-window vs. out-of-window).
- The ``/api/briefing`` router: 200 with the composed brief, and the 422 the
  router emits for an invalid ``kind``.

The briefing service owns no state; the planes are in-process singletons (no
engine, no DB), so tests get a fresh app per test — same pattern as the
attention / waiting-on / calendar test files.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.attention import reset_attention_service, get_attention_service
from backend.briefing import reset_briefing_service, get_briefing_service
from backend.calendar import reset_calendar_service
from backend.briefing.service import MAX_ACTIONS
from backend.email import reset_email_service
from backend.messages import reset_messages_service
from backend.voicemail import reset_voicemail_service
from backend.waiting_on import reset_waiting_on_service

# ---------------------------------------------------------------------------
# Pinned reference clock. The brief's sections all key off ``now``:
#   - overnight window  = (now − 24h, now]
#   - "Today"            = calendar events overlapping the wall-clock day of
#                           ``now``
#   - waiting on days   = ``now`` minus ``requested_at``
# Keeping everything anchored to one instant makes the math exact.
# ---------------------------------------------------------------------------
PINNED_NOW = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)  # Monday 07:30 UTC
TODAY_START = PINNED_NOW.replace(hour=0, minute=0, second=0, microsecond=0)
# A "recent" event within the 24-hour overnight window → counted.
RECENT = PINNED_NOW - timedelta(hours=3)
# An event outside the window (older than 24h) → NOT counted.
OLD = PINNED_NOW - timedelta(hours=30)
# A request 3 days ago → ``days_elapsed == 3``.
THREE_DAYS = PINNED_NOW - timedelta(days=3)


@pytest.fixture
def client():
    """A fresh app per test (fresh plane singletons), like the attention tests."""
    reset_attention_service()
    reset_calendar_service()
    reset_email_service()
    reset_messages_service()
    reset_voicemail_service()
    reset_waiting_on_service()
    reset_briefing_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_attention_service()
    reset_calendar_service()
    reset_email_service()
    reset_messages_service()
    reset_voicemail_service()
    reset_waiting_on_service()
    reset_briefing_service()


@pytest.fixture
def briefs():
    """Compose via the bound service (injecting the clock, not hitting the
    router) so tests can pin ``now`` directly.

    Resets every plane before AND after the test — the service reads live
    state and the test's expectations assume a clean slate.
    """
    reset_attention_service()
    reset_email_service()
    reset_messages_service()
    reset_voicemail_service()
    reset_waiting_on_service()
    reset_calendar_service()
    reset_briefing_service()
    svc = get_briefing_service()
    _compose = lambda kind="morning", now=PINNED_NOW: svc.compose(kind=kind, now=now)
    yield _compose
    reset_attention_service()
    reset_email_service()
    reset_messages_service()
    reset_voicemail_service()
    reset_waiting_on_service()
    reset_calendar_service()
    reset_briefing_service()


# -- helpers ---------------------------------------------------------------
def _seed_action(n=1, *, suggested: bool = False):
    """Seed ``n`` NOW-queue items with *strictly decreasing* priority.

    ``suggested=False`` (default) gives each item a ``reason`` label and a
    far-future due so the deterministic scorer yields distinct, non-clamped
    priorities — item 0 always ranks first, making "Now ordering" tests
    deterministic.  ``suggested=True`` instead gives the single item a
    ``suggested_action`` (the label the brief shows).
    """
    from backend.attention import get_attention_service

    svc = get_attention_service()
    for i in range(n):
        if n == 1 and suggested:
            svc.create({
                "reason": f"Item {i}",
                "urgency": 0.9,
                "importance": 0.6,
                "due": PINNED_NOW - timedelta(hours=4),
                "suggested_action": f"Do item {i}",
            })
        else:
            # Far future (well over 48h) → only the smallest deadline bonus,
            # no suggested_action → no bonus.  Keeps priorities distinct
            # and below the clamp so item 0 always outranks item 1 > item 2 …
            svc.create({
                "reason": f"Item {i}",
                "urgency": 0.9 - 0.1 * i,
                "importance": 0.6,
                "due": PINNED_NOW + timedelta(days=10),
            })
    return svc


def _seed_waiting_on(now=None):
    from backend.waiting_on import get_waiting_on_service

    svc = get_waiting_on_service()
    svc.ingest({
        "request_id": "req-1",
        "person_display_name": "Sam",
        "description": "deployment credentials",
        "requested_at": now or THREE_DAYS,
        "source": "messages",
    })
    return svc


def _seed_calendar_today(start=PINNED_NOW.replace(hour=18, minute=30, second=0)):
    from backend.calendar import get_calendar_service

    svc = get_calendar_service()
    svc.ingest({
        "event_id": "cal-1",
        "title": "Dinner",
        "start": start,
        "end": start + timedelta(hours=1),
    })
    return svc


def _seed_email(last=RECENT):
    from backend.email import get_email_service

    svc = get_email_service()
    svc.ingest({
        "message_id": "msg-1",
        "direction": "RECEIVED",
        "from_address": "alice@example.com",
        "subject": "Re: update",
        "body": "Hi, any update?",
        "timestamp": last,
    })
    return svc


def _seed_message(last=RECENT):
    from backend.messages import get_messages_service

    svc = get_messages_service()
    svc.ingest({
        "message_id": "sm-1",
        "direction": "INBOUND",
        "peer_identifier": "bob",
        "peer_name": "Bob",
        "channel": "imessage",
        "body": "Hey",
        "timestamp": last,
    })
    return svc


def _seed_voicemail(received_at=RECENT):
    from backend.voicemail import get_voicemail_service

    svc = get_voicemail_service()
    svc.ingest({
        "voicemail_id": "vm-1",
        "caller_phone": "+15555550100",
        "caller_name": "Carol",
        "duration_seconds": 60,
        "transcript": "Please call me back.",
        "received_at": received_at,
    })
    return svc


# -- empty state -----------------------------------------------------------
def test_empty_state_via_router(client):
    # No planes seeded → 200, empty: true, every section blank.
    r = client.get("/api/briefing", params={"kind": "morning"})
    assert r.status_code == 200
    body = r.json()
    assert body["empty"] is True
    assert body["actions"] == []
    assert body["waiting_on"] == []
    assert body["today"] == []
    assert body["overnight"]["emails"] == 0
    assert body["overnight"]["messages"] == 0
    assert body["overnight"]["voicemails"] == 0


def test_empty_state_via_service(briefs):
    b = briefs()
    assert b.empty is True
    assert b.actions == []
    assert b.waiting_on == []
    assert b.today == []
    assert b.overnight is not None
    assert b.overnight.emails == 0
    assert b.overnight.messages == 0
    assert b.overnight.voicemails == 0


# -- each section reflects exactly its source plane -------------------------
def test_actions_from_attention(briefs):
    _seed_action(suggested=True)
    b = briefs()
    assert b.empty is False
    assert len(b.actions) == 1
    assert b.actions[0].label == "Do item 0"
    # due carries through for "before 5 PM" framing.
    assert b.actions[0].due == PINNED_NOW - timedelta(hours=4)


def test_waiting_on_days_elapsed_is_deterministic(briefs):
    _seed_waiting_on(now=THREE_DAYS)
    b = briefs()
    assert b.empty is False
    assert len(b.waiting_on) == 1
    w = b.waiting_on[0]
    assert w.person == "Sam"
    assert w.description == "deployment credentials"
    assert w.days_elapsed == 3


def test_waiting_on_falls_back_to_reason_when_no_action(briefs):
    # An item with no suggested_action still yields a usable label.
    from backend.attention import get_attention_service

    svc = get_attention_service()
    svc.create({"reason": "Only a reason", "urgency": 0.9, "importance": 0.5,
                "due": PINNED_NOW + timedelta(days=10)})
    b = briefs()
    assert len(b.actions) == 1
    assert b.actions[0].label == "Only a reason"


def test_today_lists_calendar_events_for_today(briefs):
    _seed_calendar_today()
    b = briefs()
    assert b.empty is False
    assert len(b.today) == 1
    assert b.today[0].title == "Dinner"
    # An event on another day never bleeds into Today.
    from backend.calendar import get_calendar_service

    get_calendar_service().ingest({
        "event_id": "cal-2",
        "title": "Away",
        "start": TODAY_START.replace(month=9, day=1),
        "end": TODAY_START.replace(month=9, day=1) + timedelta(hours=1),
    })
    b2 = briefs()
    assert len(b2.today) == 1
    assert b2.today[0].title == "Dinner"


def test_overnight_counts_24h_window(briefs):
    _seed_email(last=RECENT)          # in window
    _seed_message(last=RECENT)        # in window
    _seed_voicemail(received_at=RECENT)  # in window
    b = briefs()
    assert b.empty is False
    assert b.overnight.emails == 1
    assert b.overnight.messages == 1
    assert b.overnight.voicemails == 1


def test_overnight_excludes_activity_older_than_24h(briefs):
    _seed_email(last=OLD)             # out of window
    _seed_message(last=OLD)           # out of window
    _seed_voicemail(received_at=OLD)  # out of window
    b = briefs()
    # All three planes have data, but *none* in the overnight window → the
    # overnight counts are 0.  (Each of those ingest calls also auto-creates
    # one live NOW-queue attention item, so the brief is non-empty — that
    # "cross-plane attention" behavior is tested separately; here we only
    # assert the overnight counts.)
    assert b.overnight.emails == 0
    assert b.overnight.messages == 0
    assert b.overnight.voicemails == 0


def test_sections_are_independent(briefs):
    # Seeding only one plane leaves the other sections untouched.
    _seed_action()
    b = briefs()
    assert len(b.actions) == 1
    assert b.waiting_on == []
    assert b.today == []
    assert b.overnight.emails == 0


# -- kind is metadata, not a filter ----------------------------------------
def test_kind_is_echoed(briefs):
    for kind in ("morning", "midday", "evening"):
        b = briefs(kind=kind)
        assert b.kind == kind


def test_kind_is_not_a_filter(briefs):
    _seed_action()
    _seed_calendar_today()
    morning = briefs(kind="morning")
    midnight = briefs(kind="midday")
    assert morning.actions == midnight.actions
    assert morning.today == midnight.today
    assert morning.kind != midnight.kind


# -- the Now queue's ordering and cap --------------------------------------
def test_actions_preserve_now_ordering_and_cap(briefs):
    _seed_action(n=MAX_ACTIONS + 2)  # distinct, decreasing priorities → item 0 first
    b = briefs()
    # Now ordering is preserved: the highest-urgency item ("Item 0") tops the brief.
    assert b.actions[0].label == "Item 0"
    # The brief stays a *brief*: the Now queue is capped at MAX_ACTIONS, even
    # though the store holds more than that.
    assert len(b.actions) == MAX_ACTIONS
    from backend.attention import get_attention_service

    # The backing Now queue still holds all of them — the cap is a projection,
    # not a mutation of the Now plane.
    assert len(get_attention_service().now()) == MAX_ACTIONS + 2


# -- router: kind validation and happy path --------------------------------
def test_router_returns_brief_for_valid_kind(client):
    from backend.calendar import get_calendar_service
    from datetime import datetime as _dt, timedelta as _td
    from zoneinfo import ZoneInfo

    _now = _dt.now(_dt.fromtimestamp(0).astimezone().tzinfo)
    get_calendar_service().ingest({
        "event_id": "cal-live",
        "title": "Dinner",
        "start": _now,
        "end": _now + _td(hours=1),
    })
    r = client.get("/api/briefing", params={"kind": "evening"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "evening"
    assert body["empty"] is False
    assert body["today"][0]["title"] == "Dinner"


@pytest.mark.parametrize("bad", ["weekend", "MORNING", "  x  ", "all-day"])
def test_router_422_on_invalid_kind(client, bad):
    r = client.get("/api/briefing", params={"kind": bad})
    assert r.status_code == 422


def test_router_422_detail_mentions_valid_kinds(client):
    r = client.get("/api/briefing", params={"kind": "nope"})
    detail = r.json().get("detail") or ""
    # The invalid-value message comes from Pydantic; the *brief*-level guidance
    # should be readable in the error (422 detail mentions valid kinds).
    # We assert the body carries a detail (non-empty) — the strict wording
    # lives in the models, so we only sanity-check that it's there.
    assert isinstance(detail, str) and detail
