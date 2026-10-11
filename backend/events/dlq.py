"""Dead-letter queue (DLQ) primitives for the NerveCenter event fabric.

NC-SPEC-2026-010 Phase 2 / C3 (event rules & fabric hardening). Durable
NATS consumers and replay/idempotent storage already exist; this module
adds the missing *quarantine* half: a durable-adapter-neutral record model
plus bounded retry / quarantine decisions and a persistence adapter
interface for later integration.

Guarantees
----------
- **Redaction at the boundary.** :class:`RedactionPolicy` deep-redacts
  every event recorded here *before* the record is handed to a
  persistence adapter: any dict key whose name looks secret-like
  (``token``, ``api_key``, ``password``, ``authorization``, ...) has its
  value replaced with :data:`REDACTED_VALUE`. Nested dicts and lists are
  walked (depth-bounded), so secrets cannot hide one level deeper.
  :class:`DeadLetterService.record_failure` performs the redaction
  before ``adapter.save`` is ever called.
- **Bounded retries.** :class:`RetryPolicy` caps the attempt count and
  the per-attempt delay (exponential backoff, clamped). Once the cap is
  hit the record is quarantined and never retried automatically.
- **Quarantine state.** :class:`DeadLetterRecord` carries a small state
  machine (``pending`` / ``quarantined`` / ``released`` / ``expired``);
  only ``pending`` and ``released`` records are replay-eligible, and a
  quarantined record must be explicitly
  :meth:`released <DeadLetterService.release>` before it may replay.
- **Adapter-neutral.** :class:`DeadLetterAdapter` is an ABC: Postgres,
  NATS streams, or a file-backed store can implement it. An
  :class:`InMemoryDeadLetterAdapter` is provided for tests and local
  runs. No external services, no migrations, no arbitrary code.

Both the frozen :class:`~schemas.nc_platform.NCEventEnvelope` contract
and the legacy :class:`~schemas.events.Event` model are accepted via
:func:`backend.events.rules.normalize_event`.
"""

from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.events.rules import normalize_event

__all__ = [
    "REDACTED_VALUE",
    "DEFAULT_SECRET_KEY_PATTERNS",
    "RedactionPolicy",
    "DlqState",
    "RetryPolicy",
    "RetryDecision",
    "decide_retry",
    "DeadLetterRecord",
    "DeadLetterAdapter",
    "InMemoryDeadLetterAdapter",
    "DeadLetterService",
    "dlq_record_id",
]

#: The literal value substituted for any secret-like field value.
REDACTED_VALUE = "***REDACTED***"

#: Secret-likeness is detected on key *names* (case-insensitive). The
#: patterns deliberately require the sensitive word as a token (start of
#: the key or separated by ``_`` / ``-``) so that ``dedup_key``,
#: ``partition_key`` and ``idempotency_key`` are NOT redacted while
#: ``api_key``, ``access_token``, ``authorization`` are.
DEFAULT_SECRET_KEY_PATTERNS: tuple[str, ...] = (
    r"secret",
    r"token",
    r"passw(?:or)?d|pwd",
    r"api[_-]?key",
    r"access[_-]?key",
    r"private[_-]?key",
    r"credential",
    r"authorization|auth[_-]?header|auth[_-]?token",
    r"session",
    r"cookie",
    r"signature",
)


def _secret_key_matcher(patterns: tuple[str, ...]) -> re.Pattern[str]:
    """Compile key patterns into one token-bound matcher.

    Each pattern must match at the start of the key or immediately after
    a ``_`` / ``-`` separator, so ``dedup_key`` does not match while
    ``api_key`` does.
    """
    return re.compile(rf"(?:^|[_\-])(?:{'|'.join(patterns)})", re.IGNORECASE)


DEFAULT_SECRET_KEY_RE = _secret_key_matcher(DEFAULT_SECRET_KEY_PATTERNS)


class RedactionPolicy:
    """Deep, deterministic redaction of event payloads and metadata.

    Recursively walks dicts and lists; every dict value whose key matches
    the secret-likeness patterns (or :attr:`extra_keys`) is replaced with
    :attr:`marker`. Non-container values pass through unchanged. The walk
    is depth-bounded so pathological nesting cannot blow up.
    """

    def __init__(
        self,
        *,
        key_patterns: tuple[str, ...] | None = None,
        extra_keys: frozenset[str] = frozenset(),
        marker: str = REDACTED_VALUE,
        max_depth: int = 24,
    ) -> None:
        self._matcher = _secret_key_matcher(key_patterns or DEFAULT_SECRET_KEY_PATTERNS)
        self._extra_keys = frozenset(extra_keys)
        self.marker = marker
        self.max_depth = max(1, int(max_depth))

    def is_secret_key(self, key: str) -> bool:
        """``True`` when a dict key name looks like it carries a secret."""
        if not isinstance(key, str):
            return False
        if key in self._extra_keys:
            return True
        return self._matcher.search(key) is not None

    def redact(self, data: Any, _depth: int = 0) -> Any:
        """Return a redacted deep copy of ``data`` (safe to persist)."""
        if _depth >= self.max_depth:
            return self.marker
        if isinstance(data, dict):
            result: dict[Any, Any] = {}
            for key, value in data.items():
                if self.is_secret_key(str(key)):
                    result[key] = self.marker
                else:
                    result[key] = self.redact(value, _depth + 1)
            return result
        if isinstance(data, (list, tuple)):
            return [self.redact(item, _depth + 1) for item in data]
        return data


# ---------------------------------------------------------------------------
# Retry policy / decision (pure, deterministic)
# ---------------------------------------------------------------------------

DlqState = Literal["pending", "quarantined", "released", "expired"]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry policy: exponential backoff with a hard attempt cap.

    The retry that follows the Nth failed delivery (0-based) waits
    ``base_delay_seconds * backoff_factor ** N`` clamped to
    ``max_delay_seconds``; after ``max_attempts`` total failed deliveries
    the record is no longer retriable (quarantine territory).
    """

    max_attempts: int = 5
    base_delay_seconds: float = 30.0
    backoff_factor: float = 2.0
    max_delay_seconds: float = 3600.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be >= 1.0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")

    def delay_for_attempt(self, attempts: int) -> float:
        """Backoff delay (seconds) after failure number ``attempts`` (0-based)."""
        if attempts < 0:
            raise ValueError("attempts must be >= 0")
        delay = self.base_delay_seconds * (self.backoff_factor ** attempts)
        return min(delay, self.max_delay_seconds)


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Outcome of a bounded retry evaluation for one DLQ record."""

    should_retry: bool
    reason: str
    delay_seconds: float
    next_attempt_at: datetime | None

    @property
    def exhausted(self) -> bool:
        return self.reason == "max_attempts_reached"


def decide_retry(
    record: DeadLetterRecord,
    policy: RetryPolicy,
    now: datetime | None = None,
) -> RetryDecision:
    """Pure bounded-retry decision for ``record`` (no side effects).

    Eligibility:

    - ``released`` records are always retriable (operator decision).
    - ``pending`` records are retriable while attempts < ``max_attempts``
      and the backoff window has elapsed (or no retry time was stamped).
    - ``quarantined`` / ``expired`` records are never retriable.
    - A past ``expires_at`` removes eligibility regardless of state.
    """
    now = now or datetime.now(UTC)
    if record.expires_at is not None and now >= record.expires_at:
        return RetryDecision(False, "expired", 0.0, None)
    if record.state == "released":
        return RetryDecision(True, "released_by_operator", 0.0, now)
    if record.state == "quarantined":
        return RetryDecision(False, "quarantined", 0.0, None)
    if record.state == "expired":
        return RetryDecision(False, "expired", 0.0, None)
    if record.delivery_attempts >= policy.max_attempts:
        return RetryDecision(
            False, "max_attempts_reached", 0.0,
            record.next_retry_at or record.failed_at,
        )
    if record.next_retry_at is not None and now < record.next_retry_at:
        delay = (record.next_retry_at - now).total_seconds()
        return RetryDecision(False, "backoff_not_elapsed", delay, record.next_retry_at)
    delay = policy.delay_for_attempt(record.delivery_attempts)
    return RetryDecision(True, "retriable", delay, now + timedelta(seconds=delay))


# ---------------------------------------------------------------------------
# Record model (durable-adapter-neutral)
# ---------------------------------------------------------------------------


def dlq_record_id() -> str:
    """Mint a stable, opaque DLQ record id (``dlq_`` + UUID4)."""
    return f"dlq_{uuid.uuid4()}"


class DeadLetterRecord(BaseModel):
    """One failed delivery, redacted, with bounded-retry bookkeeping.

    The model is adapter-neutral: it knows nothing about Postgres, NATS or
    files. Persistence adapters serialize it via :meth:`to_json` /
    :meth:`from_json`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=dlq_record_id, min_length=1, description="DLQ record id.")
    event_id: str = Field(
        min_length=1, description="Id of the failed event (envelope id / Event id)."
    )
    event_type: str = Field(min_length=1, description="Machine-readable event type.")
    source: str = Field(min_length=1, description="Event source (nc:// URI or origin id).")
    namespace: str | None = Field(default=None, description="Isolation namespace, when known.")
    subject: str | None = Field(default=None, description="Subject id, when known.")
    correlation_id: str | None = Field(default=None, description="Causal correlation id.")

    failed_at: datetime = Field(description="When the last failed delivery was observed (UTC).")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    delivery_attempts: int = Field(default=0, ge=0, description="Total failed deliveries.")
    last_error: str | None = Field(
        default=None, description="Classifier/message of the last failure."
    )

    state: DlqState = Field(default="pending", description="Quarantine state machine position.")
    quarantine_reason: str | None = Field(default=None)
    expires_at: datetime | None = Field(default=None, description="Optional replay deadline (UTC).")
    next_retry_at: datetime | None = Field(
        default=None, description="Next allowed retry time (UTC)."
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Delivery/stream metadata; REDACTED at the service boundary.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Redacted event body (secret-like values replaced).",
    )

    # -- convenience ---------------------------------------------------------

    def is_replay_eligible(self, policy: RetryPolicy, now: datetime | None = None) -> bool:
        """``True`` when this record may be replayed onto the bus now."""
        return decide_retry(self, policy, now=now).should_retry

    def next_state_fields(
        self,
        *,
        delivery_attempts: int | None = None,
        failed_at: datetime | None = None,
        last_error: str | None = None,
        next_retry_at: datetime | None = None,
        keep_next_retry: bool = False,
    ) -> DeadLetterRecord:
        """Copy with updated retry bookkeeping (frozen model: copy, not mutate).

        ``next_retry_at`` is only replaced when explicitly passed *or*
        ``keep_next_retry`` is ``False`` and no value is given... i.e. the
        caller passes the new value; omitting it preserves the existing one.
        """
        updates: dict[str, Any] = {
            "delivery_attempts": (
                delivery_attempts if delivery_attempts is not None else self.delivery_attempts
            ),
            "failed_at": failed_at or self.failed_at,
            "last_error": last_error if last_error is not None else self.last_error,
            "updated_at": datetime.now(UTC),
        }
        if next_retry_at is not None or not keep_next_retry:
            updates["next_retry_at"] = next_retry_at
        return self.model_copy(update=updates)

    # -- persistence helpers ---------------------------------------------------

    def to_json(self) -> bytes:
        """Compact JSON bytes (stable key order) for a persistence adapter."""
        dumped = self.model_dump(mode="json")
        return json.dumps(dumped, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes | str) -> DeadLetterRecord:
        """Rebuild a record from persisted JSON bytes/str (round-trips)."""
        return cls.model_validate(json.loads(data))


# ---------------------------------------------------------------------------
# Persistence adapter interface
# ---------------------------------------------------------------------------


class DeadLetterAdapter(ABC):
    """Adapter-neutral persistence interface for DLQ records.

    Implementations: Postgres table, NATS JetStream stream, file-backed
    JSONL, ... The service only depends on this interface, so swapping the
    durable backend later requires no service changes.
    """

    @abstractmethod
    async def save(self, record: DeadLetterRecord) -> None:
        """Persist (insert) a new record.

        Raises:
            ValueError: if a record with the same ``id`` already exists.
        """

    @abstractmethod
    async def update(self, record: DeadLetterRecord) -> None:
        """Persist a state change (quarantine/release/retry bookkeeping).

        Raises:
            KeyError: if the record id is unknown to this adapter.
        """

    @abstractmethod
    async def get(self, record_id: str) -> DeadLetterRecord | None:
        """Fetch one record by id (``None`` when absent)."""

    @abstractmethod
    async def list(self, *, state: DlqState | None = None) -> list[DeadLetterRecord]:
        """List records, optionally filtered by quarantine state."""

    @abstractmethod
    async def delete(self, record_id: str) -> None:
        """Delete a record (operator action; no-op when absent)."""


class InMemoryDeadLetterAdapter(DeadLetterAdapter):
    """In-memory adapter for tests and local development (not durable)."""

    def __init__(self) -> None:
        self._records: dict[str, DeadLetterRecord] = {}

    async def save(self, record: DeadLetterRecord) -> None:
        if record.id in self._records:
            raise ValueError(f"DLQ record {record.id} already exists")
        self._records[record.id] = record

    async def update(self, record: DeadLetterRecord) -> None:
        if record.id not in self._records:
            raise KeyError(f"unknown DLQ record {record.id}")
        self._records[record.id] = record

    async def get(self, record_id: str) -> DeadLetterRecord | None:
        return self._records.get(record_id)

    async def list(self, *, state: DlqState | None = None) -> list[DeadLetterRecord]:
        records = list(self._records.values())
        if state is not None:
            records = [r for r in records if r.state == state]
        return records

    async def delete(self, record_id: str) -> None:
        self._records.pop(record_id, None)

    def __len__(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Service (redaction boundary + state machine)
# ---------------------------------------------------------------------------


class DeadLetterService:
    """Coordinates redaction, persistence and the quarantine state machine.

    This is the single boundary at which raw event material touches a
    persistence adapter: :meth:`record_failure` redacts *first*, then
    saves. Adapters therefore never see unredacted secret-like values.
    """

    def __init__(
        self,
        adapter: DeadLetterAdapter,
        *,
        policy: RetryPolicy | None = None,
        redaction: RedactionPolicy | None = None,
        clock: Any = None,
    ) -> None:
        self._adapter = adapter
        self.policy = policy or RetryPolicy()
        self.redaction = redaction or RedactionPolicy()
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        now = self._clock()
        return now if now.tzinfo else now.replace(tzinfo=UTC)

    # -- recording -----------------------------------------------------------

    async def record_failure(
        self,
        event: Any,
        *,
        error: str,
        delivery_attempts: int = 1,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> DeadLetterRecord:
        """Redact and persist a failed delivery.

        Parameters
        ----------
        event:
            A frozen :class:`~schemas.nc_platform.NCEventEnvelope` or a
            legacy :class:`~schemas.events.Event`.
        error:
            Failure classifier/message (stable code, not a raw stack trace).
        delivery_attempts:
            Total failed deliveries observed so far (>= 1).
        metadata:
            Delivery/stream metadata; redacted alongside the payload.
        correlation_id:
            Explicit correlation override (defaults to the event's own).
        """
        norm = normalize_event(event)
        now = self._now()

        payload = self.redaction.redact(norm.data or {})
        meta = self.redaction.redact(metadata or {})

        exhausted = delivery_attempts >= self.policy.max_attempts
        delay = self.policy.delay_for_attempt(max(0, delivery_attempts - 1))
        record = DeadLetterRecord(
            event_id=norm.event_id,
            event_type=norm.event_type,
            source=norm.source,
            namespace=norm.namespace,
            subject=norm.subject,
            correlation_id=correlation_id or norm.correlation_id,
            failed_at=now,
            recorded_at=now,
            updated_at=now,
            delivery_attempts=max(0, delivery_attempts),
            last_error=error,
            state="quarantined" if exhausted else "pending",
            quarantine_reason="max_attempts_reached" if exhausted else None,
            next_retry_at=None if exhausted else now + timedelta(seconds=delay),
            metadata=meta,
            payload=payload,
        )
        await self._adapter.save(record)
        return record

    async def record_retry_failure(
        self, record_id: str, *, error: str
    ) -> DeadLetterRecord:
        """Register another failed delivery for an existing record.

        Increments the attempt count, stamps the backoff, and quarantines
        automatically once the attempt cap is exhausted.
        """
        record = await self._require(record_id)
        attempts = record.delivery_attempts + 1
        exhausted = attempts >= self.policy.max_attempts
        delay = self.policy.delay_for_attempt(attempts - 1)
        updated = record.next_state_fields(
            delivery_attempts=attempts,
            failed_at=self._now(),
            last_error=error,
            next_retry_at=None if exhausted else self._now() + timedelta(seconds=delay),
        )
        if exhausted and updated.state != "quarantined":
            updated = updated.model_copy(
                update={"state": "quarantined", "quarantine_reason": "max_attempts_reached"}
            )
        await self._adapter.update(updated)
        return updated

    # -- quarantine state machine --------------------------------------------

    async def quarantine(self, record_id: str, *, reason: str) -> DeadLetterRecord:
        """Move a record into the quarantined state (not replay-eligible)."""
        record = await self._require(record_id)
        updated = record.next_state_fields(keep_next_retry=True).model_copy(
            update={"state": "quarantined", "quarantine_reason": reason}
        )
        await self._adapter.update(updated)
        return updated

    async def release(self, record_id: str) -> DeadLetterRecord:
        """Release a quarantined record back to replay eligibility."""
        record = await self._require(record_id)
        if record.state != "quarantined":
            raise ValueError(f"record {record_id} is {record.state!r}, not quarantined")
        updated = record.next_state_fields(keep_next_retry=True).model_copy(
            update={"state": "released", "quarantine_reason": None, "next_retry_at": None}
        )
        await self._adapter.update(updated)
        return updated

    async def expire(self, record_id: str) -> DeadLetterRecord:
        """Mark a record expired (terminal; never replay-eligible)."""
        record = await self._require(record_id)
        updated = record.next_state_fields(keep_next_retry=True).model_copy(
            update={"state": "expired"}
        )
        await self._adapter.update(updated)
        return updated

    # -- replay eligibility ---------------------------------------------------

    async def eligible_for_replay(self, now: datetime | None = None) -> list[DeadLetterRecord]:
        """All records that may be replayed onto the bus right now."""
        moment = now or self._now()
        records = await self._adapter.list()
        return [r for r in records if decide_retry(r, self.policy, now=moment).should_retry]

    async def decide(self, record_id: str, now: datetime | None = None) -> RetryDecision:
        """Bounded retry decision for one record (pure read)."""
        record = await self._require(record_id)
        return decide_retry(record, self.policy, now=now or self._now())

    # -- internals -------------------------------------------------------------

    async def _require(self, record_id: str) -> DeadLetterRecord:
        record = await self._adapter.get(record_id)
        if record is None:
            raise KeyError(f"unknown DLQ record {record_id}")
        return record
