"""C3: bounded DLQ / quarantine primitives (backend/events/dlq.py).

Coverage
--------
- secret-like redaction at the persistence boundary (deep, nested,
  case-insensitive, token-bound so ``dedup_key`` survives);
- bounded retry policy (backoff clamp, attempt cap, exhaustion);
- quarantine state machine (pending -> quarantined -> released / expired);
- replay eligibility (released always, pending by backoff window);
- adapter-neutral record serialization round-trip;
- in-memory adapter semantics (save/update/get/list/delete).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.events.dlq import (
    REDACTED_VALUE,
    DeadLetterAdapter,
    DeadLetterRecord,
    DeadLetterService,
    InMemoryDeadLetterAdapter,
    RedactionPolicy,
    RetryPolicy,
    decide_retry,
    dlq_record_id,
)
from schemas.events import Event
from schemas.nc_platform import NCEventEnvelope, NcEventExtension

_ULID = "01ARZ3NDEKTSV4RRFFQ6JDG1JQ"
# Two further valid 26-char Crockford ULID bodies for multi-event tests.
_ULID_B = "01ARZ3NDEKTSV4RRFFQ6JDG2AB"
_ULID_C = "01ARZ3NDEKTSV4RRFFQ6JDG3CD"
NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=UTC)


def make_envelope(
    *,
    event_id: str = _ULID,
    event_type: str = "nc.device.state.changed",
    correlation_id: str | None = "corr-1",
    data: dict | None = None,
) -> NCEventEnvelope:
    return NCEventEnvelope(
        id=f"evt_{event_id}",
        source="nc://personal/homeassistant/home/devices/bedroom-lamp",
        type=event_type,
        data=data if data is not None else {"state": "on"},
        nc=NcEventExtension(
            namespace="personal", classification="PUBLIC", correlation_id=correlation_id
        ),
    )


def make_legacy(
    *,
    payload: dict | None = None,
    correlation_id: str | None = None,
) -> Event:
    return Event(
        id="evt-legacy-1",
        event_type="task.completed",
        category="task",
        source="orion.tasks",
        stream="personal",
        payload=payload if payload is not None else {"state": "done"},
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedaction:
    SECRET_PAYLOAD = {
        "api_key": "sk-live-1234567890",
        "state": "on",
        "region": "us-east-1",
        "dedup_key": "dk-keep-me",  # must NOT be redacted (token-bound match)
        "idempotency_key": "ik-keep-me",  # must NOT be redacted
        "partition_key": "pk-keep-me",  # must NOT be redacted
        "nested": {
            "access_token": "Bearer xyz",
            "authorization": "Bearer abc",
            "session_id": "sess-42",
            "cookie": "sid=42",
            "password": "hunter2",
            # "credentials" matches the ``credential`` pattern: the WHOLE
            # value is replaced (recursion stops there).
            "credentials": {"password": "hunter2"},
            "items": [
                {"private_key": "PEM", "note": "ok"},
                {"api-key": "dash-style"},
            ],
        },
    }

    def test_deep_redaction_of_secret_like_keys(self) -> None:
        policy = RedactionPolicy()
        result = policy.redact(self.SECRET_PAYLOAD)

        assert result["api_key"] == REDACTED_VALUE
        assert result["state"] == "on"  # non-secret untouched
        # token-bound matching preserves dedup / idempotency / partition keys
        assert result["dedup_key"] == "dk-keep-me"
        assert result["idempotency_key"] == "ik-keep-me"
        assert result["partition_key"] == "pk-keep-me"
        # nested dicts
        assert result["nested"]["access_token"] == REDACTED_VALUE
        assert result["nested"]["authorization"] == REDACTED_VALUE
        assert result["nested"]["session_id"] == REDACTED_VALUE
        assert result["nested"]["cookie"] == REDACTED_VALUE
        assert result["nested"]["password"] == REDACTED_VALUE
        # "credential" pattern: the WHOLE value is replaced, no recursion inside
        assert result["nested"]["credentials"] == REDACTED_VALUE
        # nested lists of dicts
        assert result["nested"]["items"][0]["private_key"] == REDACTED_VALUE
        assert result["nested"]["items"][0]["note"] == "ok"
        assert result["nested"]["items"][1]["api-key"] == REDACTED_VALUE

    def test_case_insensitive_key_detection(self) -> None:
        policy = RedactionPolicy()
        assert policy.is_secret_key("API_KEY")
        assert policy.is_secret_key("Access-Token")
        assert policy.is_secret_key("cookie")
        assert policy.is_secret_key("SessionId")
        assert not policy.is_secret_key("dedup_key")
        assert not policy.is_secret_key("partition_key")
        assert not policy.is_secret_key("idempotency_key")

    def test_extra_keys_are_always_redacted(self) -> None:
        policy = RedactionPolicy(extra_keys=frozenset({"home_address"}))
        assert policy.is_secret_key("home_address")
        assert not policy.is_secret_key("home_number")
        result = policy.redact({"home_address": "1 Main St", "home_number": 1})
        assert result["home_address"] == REDACTED_VALUE
        assert result["home_number"] == 1

    def test_redaction_is_deep_copy_not_in_place(self) -> None:
        policy = RedactionPolicy()
        original = {"api_key": "sk", "nested": {"token": "t"}}
        result = policy.redact(original)
        assert original["api_key"] == "sk"  # source untouched
        assert result is not original

    def test_depth_bounding(self) -> None:
        policy = RedactionPolicy(max_depth=2)
        # Structure: {"a": {"b": {"token": "x", "plain": 1}}}
        # - depth 0: outer dict
        # - depth 1: inner dict {"b": {...}}
        # - depth 2: innermost dict -> replaced by the marker (depth-bounded)
        result = policy.redact({"a": {"b": {"token": "x", "plain": 1}}})
        assert result["a"]["b"] == REDACTED_VALUE

    def test_marker_is_constant(self) -> None:
        assert REDACTED_VALUE == "***REDACTED***"


# ---------------------------------------------------------------------------
# Retry policy / decision (pure)
# ---------------------------------------------------------------------------


def _record(
    *,
    state: str = "pending",
    attempts: int = 0,
    next_retry_at: datetime | None = None,
    expires_at: datetime | None = None,
    failed_at: datetime = NOW,
) -> DeadLetterRecord:
    return DeadLetterRecord(
        event_id="evt_" + _ULID,
        event_type="nc.x",
        source="nc://personal/homeassistant/home/devices/bedroom-lamp",
        state=state,  # type: ignore[arg-type]
        delivery_attempts=attempts,
        next_retry_at=next_retry_at,
        expires_at=expires_at,
        failed_at=failed_at,
        payload={"state": "on"},
    )


class TestRetryDecision:
    def test_backoff_grows_and_clamps(self) -> None:
        policy = RetryPolicy(base_delay_seconds=10.0, backoff_factor=2.0, max_delay_seconds=60.0)
        assert policy.delay_for_attempt(0) == 10.0
        assert policy.delay_for_attempt(1) == 20.0
        assert policy.delay_for_attempt(3) == 60.0  # clamped
        assert policy.delay_for_attempt(20) == 60.0

    def test_policy_validation(self) -> None:
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValueError):
            RetryPolicy(base_delay_seconds=0.0, backoff_factor=0.5)
        with pytest.raises(ValueError):
            RetryPolicy(base_delay_seconds=100.0, max_delay_seconds=10.0)

    def test_pending_retriable_after_backoff(self) -> None:
        policy = RetryPolicy()
        rec = _record(attempts=1, next_retry_at=NOW + timedelta(seconds=30))
        early = decide_retry(rec, policy, now=NOW)
        assert not early.should_retry
        assert early.reason == "backoff_not_elapsed"
        assert early.delay_seconds == pytest.approx(30.0)
        later = decide_retry(rec, policy, now=NOW + timedelta(seconds=31))
        assert later.should_retry
        assert later.reason == "retriable"

    def test_attempt_cap_exhausts(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        rec = _record(attempts=3, next_retry_at=NOW - timedelta(seconds=1))
        decision = decide_retry(rec, policy, now=NOW)
        assert not decision.should_retry
        assert decision.exhausted
        assert decision.reason == "max_attempts_reached"

    def test_states_gate_replay(self) -> None:
        policy = RetryPolicy()
        assert not decide_retry(_record(state="quarantined"), policy, now=NOW).should_retry
        assert not decide_retry(_record(state="expired"), policy, now=NOW).should_retry
        released = decide_retry(_record(state="released"), policy, now=NOW)
        assert released.should_retry
        assert released.reason == "released_by_operator"

    def test_expiry_overrides_everything(self) -> None:
        policy = RetryPolicy()
        rec = _record(state="released", expires_at=NOW - timedelta(seconds=1))
        decision = decide_retry(rec, policy, now=NOW)
        assert not decision.should_retry
        assert decision.reason == "expired"


# ---------------------------------------------------------------------------
# Service: redaction boundary + state machine
# ---------------------------------------------------------------------------


class TestDeadLetterService:
    async def test_record_failure_redacts_before_persist(self) -> None:
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, clock=lambda: NOW)
        event = make_envelope(
            data={
                "api_key": "sk-live-123",
                "state": "on",
                "auth_token": "t-1",
                "dedup_key": "keep",
            }
        )
        record = await service.record_failure(event, error="nats:timeout", delivery_attempts=1)

        assert record.payload["api_key"] == REDACTED_VALUE
        assert record.payload["auth_token"] == REDACTED_VALUE
        assert record.payload["dedup_key"] == "keep"
        assert record.payload["state"] == "on"
        assert record.event_id == "evt_" + _ULID
        assert record.correlation_id == "corr-1"
        assert record.state == "pending"
        assert record.last_error == "nats:timeout"
        assert len(adapter) == 1
        # the adapter never saw the raw secret
        assert "sk-live-123" not in record.to_json().decode("utf-8")

    async def test_record_failure_with_metadata_redacts_metadata(self) -> None:
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, clock=lambda: NOW)
        record = await service.record_failure(
            make_legacy(payload={"n": 1}),
            error="stream:missing",
            metadata={"partition_key": "p1", "session_cookie": "sid=9"},
        )
        assert record.metadata["partition_key"] == "p1"
        assert record.metadata["session_cookie"] == REDACTED_VALUE
        assert record.payload == {"n": 1}

    async def test_retry_failure_increments_and_quarantines_at_cap(self) -> None:
        policy = RetryPolicy(max_attempts=3, base_delay_seconds=1.0)
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, policy=policy, clock=lambda: NOW)
        record = await service.record_failure(make_envelope(), error="e1", delivery_attempts=1)

        r2 = await service.record_retry_failure(record.id, error="e2")
        assert r2.delivery_attempts == 2
        assert r2.state == "pending"
        assert r2.last_error == "e2"
        assert r2.next_retry_at is not None and r2.next_retry_at > NOW

        r3 = await service.record_retry_failure(record.id, error="e3")
        assert r3.delivery_attempts == 3
        assert r3.state == "quarantined"
        assert r3.quarantine_reason == "max_attempts_reached"
        assert r3.next_retry_at is None

    async def test_quarantine_release_expire_transitions(self) -> None:
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, clock=lambda: NOW)
        record = await service.record_failure(make_envelope(), error="e")

        quarantined = await service.quarantine(record.id, reason="operator_review")
        assert quarantined.state == "quarantined"
        # quarantined records are not replay-eligible
        decision = await service.decide(record.id, now=NOW + timedelta(minutes=10))
        assert decision.reason == "quarantined"

        released = await service.release(record.id)
        assert released.state == "released"
        assert (await service.decide(record.id, now=NOW)).should_retry

        expired = await service.expire(record.id)
        assert expired.state == "expired"
        assert not (await service.decide(record.id, now=NOW)).should_retry

        with pytest.raises(ValueError):
            await service.release(record.id)  # expired, not quarantined

    async def test_eligible_for_replay_lists_only_retriable(self) -> None:
        policy = RetryPolicy(max_attempts=5, base_delay_seconds=30.0)
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, policy=policy, clock=lambda: NOW)
        pending = await service.record_failure(
            make_envelope(event_id=_ULID_B), error="e", delivery_attempts=1
        )
        exhausted = await service.record_failure(
            make_envelope(event_id=_ULID_C), error="e", delivery_attempts=5
        )
        assert exhausted.state == "quarantined"

        eligible = await service.eligible_for_replay(now=NOW + timedelta(minutes=5))
        assert {r.event_id for r in eligible} == {pending.event_id}

    async def test_unknown_record_id_raises(self) -> None:
        service = DeadLetterService(InMemoryDeadLetterAdapter(), clock=lambda: NOW)
        with pytest.raises(KeyError):
            await service.quarantine("dlq_missing", reason="x")

    async def test_release_requires_quarantined(self) -> None:
        adapter = InMemoryDeadLetterAdapter()
        service = DeadLetterService(adapter, clock=lambda: NOW)
        record = await service.record_failure(make_envelope(), error="e")
        with pytest.raises(ValueError):
            await service.release(record.id)


# ---------------------------------------------------------------------------
# Record model + adapter semantics
# ---------------------------------------------------------------------------


class TestRecordAndAdapter:
    def test_record_id_shape(self) -> None:
        assert dlq_record_id().startswith("dlq_")
        assert len(dlq_record_id()) > len("dlq_")

    def test_json_round_trip(self) -> None:
        record = _record(attempts=2, next_retry_at=NOW + timedelta(seconds=90))
        rebuilt = DeadLetterRecord.from_json(record.to_json())
        assert rebuilt == record
        assert rebuilt.delivery_attempts == 2
        assert rebuilt.next_retry_at == NOW + timedelta(seconds=90)

    def test_record_is_frozen(self) -> None:
        record = _record()
        with pytest.raises(ValidationError):
            record.state = "released"  # type: ignore[misc]

    async def test_in_memory_adapter_semantics(self) -> None:
        adapter = InMemoryDeadLetterAdapter()
        record = _record()

        await adapter.save(record)
        with pytest.raises(ValueError):
            await adapter.save(record)  # duplicate id

        assert (await adapter.get(record.id)) == record
        assert (await adapter.get("dlq_nope")) is None

        updated = record.next_state_fields(
            delivery_attempts=1, failed_at=NOW + timedelta(seconds=1)
        )
        await adapter.update(updated)
        assert (await adapter.get(record.id)) == updated
        with pytest.raises(KeyError):
            await adapter.update(_record())  # unknown id

        assert {r.id for r in await adapter.list()} == {record.id}
        assert await adapter.list(state="quarantined") == []
        quarantined = record.next_state_fields(keep_next_retry=True).model_copy(
            update={"state": "quarantined", "quarantine_reason": "x"}
        )
        await adapter.update(quarantined)
        assert [r.id for r in await adapter.list(state="quarantined")] == [record.id]

        await adapter.delete(record.id)
        assert await adapter.get(record.id) is None
        await adapter.delete(record.id)  # no-op

    async def test_adapter_interface_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            DeadLetterAdapter()  # type: ignore[abstract]
