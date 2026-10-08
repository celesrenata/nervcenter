"""T-H32: GET /api/events is backed by the live NATS JetStream event bus.

No live NATS is used: the endpoint is exercised against an in-memory
:class:`InMemoryNatsClient` fake that implements the same
``jetstream`` / ``config`` surface :class:`backend.events.nats_client.NatsClient`
exposes (``stream_info`` + bounded ``get_msg``).  Seed data uses the real
wire envelope (:func:`backend.events.models.encode_event`), so the read
path is end-to-end except for the socket.

Coverage
--------
- real rows surface from the bus (order, pagination, entity filter, limit);
- honest degradation: bus absent → empty 200 (total=0); bus unreachable /
  stream missing / read timeout → 503 ``event_bus_unavailable`` (no fake
  success, no fabricated events);
- spec §10 immutability: ``Event`` is frozen; the publisher still works on
  frozen events (regression guard for the freeze).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.api.endpoints import events as events_module
from backend.events.models import encode_event
from backend.events.nats_client import NATSConfig
from backend.events.publisher import EventPublisher
from backend.events.query import EventBusError
from backend.events.query import list_events as bus_list_events
from schemas.events import Event

LISTING_URL = "/api/events/"


# ---------------------------------------------------------------------------
# In-memory bus fake
# ---------------------------------------------------------------------------


class _InMemoryJetStream:
    """Stands in for the NATS JetStream context used by the listing path."""

    def __init__(self, *, fail_stream_info: Exception | None = None, get_msg_delay: float = 0.0):
        self.messages: dict[tuple[str, int], SimpleNamespace] = {}
        self._next_seq = 1
        self.fail_stream_info = fail_stream_info
        self.get_msg_delay = get_msg_delay
        self.publish_log: list[tuple[str, bytes, Any]] = []

    def append(self, stream: str, subject: str, data: bytes) -> int:
        seq = self._next_seq
        self._next_seq += 1
        self.messages[(stream, seq)] = SimpleNamespace(subject=subject, seq=seq, data=data)
        return seq

    async def stream_info(self, name: str, subjects_filter: str | None = None) -> Any:
        if self.fail_stream_info is not None:
            raise self.fail_stream_info
        total = len(self.messages)
        last = max((seq for (stream, seq) in self.messages if stream == name), default=0)
        return SimpleNamespace(state=SimpleNamespace(messages=total, last_seq=last, first_seq=1))

    async def get_msg(
        self,
        stream_name: str,
        seq: int | None = None,
        subject: str | None = None,
        direct: bool = False,
        next: bool = False,
    ) -> Any:
        if seq is None:
            raise ValueError("seq is required")
        if self.get_msg_delay:
            await asyncio.sleep(self.get_msg_delay)
        msg = self.messages.get((stream_name, seq))
        if msg is None:
            raise RuntimeError(f"no message at seq {seq}")
        return msg

    async def publish(self, subject: str, data: bytes, headers: Any = None) -> Any:
        self.publish_log.append((subject, data, headers))
        return SimpleNamespace(
            stream=self._stream_name_for(subject), sequence=len(self.publish_log)
        )

    def _stream_name_for(self, subject: str) -> str:
        return "NERVECENTER_EVENTS"


@dataclass
class InMemoryNatsClient:
    """In-memory stand-in for :class:`backend.events.nats_client.NatsClient`.

    Exposes the two attributes the listing helper relies on: ``config``
    (a real :class:`NATSConfig`) and the ``jetstream`` property (raising
    ``RuntimeError`` when not connected, mirroring the real client).
    """

    connected: bool = True
    fail_stream_info: Exception | None = None
    get_msg_delay: float = 0.0
    js: _InMemoryJetStream = field(init=False)
    config: NATSConfig = field(init=False)

    def __post_init__(self) -> None:
        self.js = _InMemoryJetStream(
            fail_stream_info=self.fail_stream_info,
            get_msg_delay=self.get_msg_delay,
        )
        self.config = NATSConfig()

    @property
    def jetstream(self) -> Any:
        if not self.connected:
            raise RuntimeError("NatsClient is not connected. Call connect() first.")
        return self.js

    def seed(self, event: Event, subject: str | None = None) -> int:
        subject = subject or self.config.subject_for_event(event.category, event.event_type)
        data = encode_event(event, subject=subject)
        return self.js.append(self.config.stream_name, subject, data)


def make_event(
    event_id: str,
    *,
    event_type: str = "task.completed",
    subject: str | None = None,
    category: str = "task",
    source: str = "internal",
) -> Event:
    """Build a canonical §10 event (fingerprinted, correlation/trace set)."""
    ts = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
    event = Event(
        id=event_id,
        created_at=ts,
        event_type=event_type,
        category=category,
        occurred_at=ts,
        source=source,
        subject=subject,
        payload={"note": event_id},
    )
    staged = event.model_copy(
        update={
            "correlation_id": f"corr-{event_id}",
            "trace_id": f"trace-{event_id}",
        }
    )
    # The integrity hash must cover the final field set (incl. correlation/trace).
    event = staged.model_copy(update={"hash": staged.fingerprint()})
    assert event.verify_integrity()
    return event


def make_app(nats_client: Any) -> FastAPI:
    """Bare FastAPI app mounting only the events router (state injected)."""
    app = FastAPI()
    app.state.nats_client = nats_client
    app.include_router(events_module.router)
    return app


# ---------------------------------------------------------------------------
# Listing: real rows surface
# ---------------------------------------------------------------------------


def test_list_events_returns_real_rows_from_bus() -> None:
    bus = InMemoryNatsClient()
    for i in range(1, 4):
        bus.seed(make_event(f"evt-{i}", subject=f"entity-{i % 2}"))
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["data"], list) and len(body["data"]) == 3
    # Stream order: oldest first.
    assert [row["id"] for row in body["data"]] == ["evt-1", "evt-2", "evt-3"]

    row = body["data"][0]
    # §10 immutable schema fields surface on the wire.
    for key in (
        "id",
        "event_type",
        "category",
        "occurred_at",
        "source",
        "subject",
        "payload",
        "severity",
        "trace_id",
        "correlation_id",
        "parent_event_id",
        "stream",
        "sequence",
        "schema_version",
        "hash",
        "created_at",
    ):
        assert key in row, f"missing §10 field {key!r}"
    assert row["hash"] == make_event("evt-1", subject="entity-1").fingerprint()

    meta = body["meta"]
    assert meta["pagination"]["total"] == 3
    assert meta["pagination"]["returned"] == 3
    assert meta["version"] == "1.0.0"


def test_list_events_limit_bounds_the_window() -> None:
    bus = InMemoryNatsClient()
    for i in range(1, 6):
        bus.seed(make_event(f"evt-{i}"))
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL, params={"limit": 2})
    assert res.status_code == 200
    body = res.json()
    # Most recent 2, still oldest-first within the window; total stays honest.
    assert [row["id"] for row in body["data"]] == ["evt-4", "evt-5"]
    assert body["meta"]["pagination"]["total"] == 5
    assert body["meta"]["pagination"]["returned"] == 2


def test_list_events_entity_filter_filters_by_subject() -> None:
    bus = InMemoryNatsClient()
    bus.seed(make_event("evt-a1", subject="entity-a"))
    bus.seed(make_event("evt-b1", subject="entity-b"))
    bus.seed(make_event("evt-a2", subject="entity-a"))
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL, params={"entity": "entity-a"})
    assert res.status_code == 200
    body = res.json()
    assert [row["id"] for row in body["data"]] == ["evt-a1", "evt-a2"]
    # Total reflects the whole stream, not the filter (honest stream state).
    assert body["meta"]["pagination"]["total"] == 3


def test_list_events_empty_stream_is_honest_empty() -> None:
    bus = InMemoryNatsClient()  # connected, zero messages
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL)
    assert res.status_code == 200
    body = res.json()
    assert body["data"] == []
    assert body["meta"]["pagination"]["total"] == 0
    assert body["meta"]["pagination"]["returned"] == 0


# ---------------------------------------------------------------------------
# Honest degradation
# ---------------------------------------------------------------------------


def test_list_events_bus_not_configured_degrades_to_empty() -> None:
    client = TestClient(make_app(None))  # app.state.nats_client unset

    res = client.get(LISTING_URL)
    assert res.status_code == 200
    body = res.json()
    assert body["data"] == []
    assert body["meta"]["pagination"]["total"] == 0


def test_list_events_unreachable_bus_is_503_not_fake_success() -> None:
    bus = InMemoryNatsClient(connected=False)  # jetstream access raises
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL)
    assert res.status_code == 503
    body = res.json()
    assert body["error"] == "event_bus_unavailable"
    assert "detail" in body and body["detail"]
    assert "data" not in body  # no list envelope, no fabricated rows


def test_list_events_stream_missing_is_503() -> None:
    bus = InMemoryNatsClient(fail_stream_info=ConnectionError("stream not found"))
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL)
    assert res.status_code == 503
    assert res.json()["error"] == "event_bus_unavailable"


def test_list_events_read_timeout_degrades_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    import backend.events.query as query_module

    bus = InMemoryNatsClient(get_msg_delay=5.0)  # far beyond the bounded window
    bus.seed(make_event("evt-1"))
    monkeypatch.setattr(query_module, "BUS_READ_TIMEOUT_S", 0.05)
    client = TestClient(make_app(bus))

    res = client.get(LISTING_URL)
    assert res.status_code == 503
    assert res.json()["error"] == "event_bus_unavailable"


def test_get_event_found_via_bus() -> None:
    bus = InMemoryNatsClient()
    bus.seed(make_event("evt-keep"))
    bus.seed(make_event("evt-keep2"))
    client = TestClient(make_app(bus))

    res = client.get("/api/events/evt-keep")
    assert res.status_code == 200
    row = res.json()
    assert row["id"] == "evt-keep"
    assert row["event_type"] == "task.completed"
    assert row["payload"] == {"note": "evt-keep"}


def test_get_event_not_in_window_is_404_not_fabricated() -> None:
    bus = InMemoryNatsClient()
    bus.seed(make_event("evt-other"))
    client = TestClient(make_app(bus))

    res = client.get("/api/events/evt-ghost")
    assert res.status_code == 404


def test_get_event_bus_not_configured_is_404() -> None:
    client = TestClient(make_app(None))
    res = client.get("/api/events/evt-1")
    assert res.status_code == 404


def test_get_event_unreachable_bus_is_503() -> None:
    bus = InMemoryNatsClient(connected=False)
    client = TestClient(make_app(bus))

    res = client.get("/api/events/evt-1")
    assert res.status_code == 503
    assert res.json()["error"] == "event_bus_unavailable"


# ---------------------------------------------------------------------------
# Query-layer behavior (bounded reads)
# ---------------------------------------------------------------------------


async def test_query_layer_raises_eventbuserror_when_not_connected() -> None:
    bus = InMemoryNatsClient(connected=False)
    with pytest.raises(EventBusError, match="not connected"):
        await bus_list_events(bus)


async def test_query_layer_partial_window_on_late_failure() -> None:
    bus = InMemoryNatsClient()
    for i in range(1, 4):
        bus.seed(make_event(f"evt-{i}"))
    # Corrupt the last message so its read fails after two succeed.
    bus.js.messages[("NERVECENTER_EVENTS", 3)] = SimpleNamespace(
        subject="nervcenter.task.task.completed", seq=3, data=b"\x00garbage"
    )
    result = await bus_list_events(bus)
    assert [e.id for e in result.events] == ["evt-1", "evt-2"]
    assert result.total == 3
    assert result.truncated is True


# ---------------------------------------------------------------------------
# Spec §10: frozen immutable event schema
# ---------------------------------------------------------------------------


def test_event_schema_is_frozen() -> None:
    event = make_event("evt-frozen")

    with pytest.raises(ValidationError):
        event.event_type = "task.other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        event.hash = None  # type: ignore[assignment]
    with pytest.raises(ValidationError):
        event.payload = {"other": 1}  # type: ignore[assignment]

    # Immutability does not break derivation (publisher-style model_copy).
    derived = event.model_copy(update={"correlation_id": "corr-new"})
    assert derived.correlation_id == "corr-new"
    assert event.correlation_id == "corr-evt-frozen"


async def test_publisher_works_on_frozen_events() -> None:
    bus = InMemoryNatsClient()
    publisher = EventPublisher(bus)

    # Publish a *correlation-less* event: the publisher must derive correlation/
    # trace/hash without mutating the source record.
    bare = make_event("evt-bare").model_copy(
        update={"correlation_id": None, "trace_id": None, "hash": None}
    )

    result = await publisher.publish(bare)
    assert result.success is True

    subject, data, _ = bus.js.publish_log[0]
    assert subject == "nervcenter.task.task.completed"
    from backend.events.models import decode_event

    on_wire = decode_event(data)
    assert on_wire.correlation_id is not None
    assert on_wire.trace_id is not None
    assert on_wire.hash is not None and on_wire.verify_integrity()
    # The source record was never touched (immutability preserved).
    assert bare.correlation_id is None
    assert bare.hash is None


def test_no_hardcoded_fixtures_remain() -> None:
    """Regression guard: the endpoint source no longer contains evt-1/evt-2."""
    import inspect

    source = inspect.getsource(events_module)
    assert "evt-1" not in source
    assert "evt-2" not in source


# ---------------------------------------------------------------------------
# Integration: real app wiring, bus env unset → honest empty listing
# ---------------------------------------------------------------------------


ENV_NAMES = (
    "NERVE_DB_URL",
    "NERVECENTER_DATABASE_URL",
    "NERVE_NATS_URL",
    "NERVECENTER_NATS_URL",
)


def test_real_app_without_bus_returns_honest_empty() -> None:
    from backend.api.app import app as module_app

    for name in ENV_NAMES:
        __import__("os").environ.pop(name, None)

    with TestClient(module_app) as client:
        res = client.get(LISTING_URL)
        assert res.status_code == 200
        body = res.json()
        assert body["data"] == []
        assert body["meta"]["pagination"]["total"] == 0
