"""Event wire models for the NerveCenter event bus.

This module defines the wire-level data structures used when events are
serialized onto the NATS event bus. It complements the Pydantic
:class:`~schemas.events.Event` contract (Section 10) with:

- :class:`EventEnvelope` — the JSON envelope sent over the wire, wrapping
  the event payload with delivery metadata (publish time, delivery attempts,
  NATS subject, etc.).
- :class:`ReplayRequest` — parameters for a durable replay from a stream.
- :class:`ReplayResult` — the outcome of a replay operation.
- :class:`DeliveryMetadata` — NATS JetStream delivery metadata attached to
  each consumed message (stream, sequence, timestamp, redelivery count).
- :func:`encode_event` — serialize an :class:`~schemas.events.Event` to the
  wire envelope bytes.
- :func:`decode_event` — deserialize wire bytes back into an
  :class:`~schemas.events.Event`.
- :func:`generate_correlation_id` — create a new correlation ID for a
  logical unit of work.

The envelope is designed so that downstream consumers can:

1. Validate the event integrity via its SHA-256 hash.
2. Propagate the ``correlation_id`` and ``trace_id`` to subsequent events.
3. Deduplicate by ``idempotency_key`` on redelivery.
4. Order by ``stream`` / ``sequence`` for replay.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from schemas.events import Event


# ---------------------------------------------------------------------------
# Correlation helpers
# ---------------------------------------------------------------------------


def generate_correlation_id() -> str:
    """Generate a new UUID4 correlation ID for a logical unit of work.

    Returns
    -------
    str
        A 32-character hex UUID4 string.
    """
    return str(uuid.uuid4())


def new_trace_id() -> str:
    """Generate a new trace ID for a distributed trace."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Delivery metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeliveryMetadata:
    """Metadata about the delivery of a single event message.

    This mirrors the JetStream delivery info header that NATS attaches to
    every JetStream-delivered message (``Nats-JS-Stream``, ``Nats-JS-Sequence``,
    ``Nats-JS-Time-Stamp``, ``Nats-Status``, ``Nats-Expected-Stream``, ...).

    Attributes
    ----------
    stream:
        JetStream stream name that delivered this message.
    sequence:
        Stream sequence number of the message.
    consumer_sequence:
        Consumer sequence number (``0`` if this is the first delivery).
    timestamp:
        When the message was first published (UTC).
    redelivery:
        ``True`` when this delivery is a redelivery (``Nats-Num-Delivered > 1``).
    num_delivered:
        How many times this message has been delivered.
    pending:
        Total number of messages pending in the consumer at delivery time.
    subject:
        NATS subject the message was published to.
    """

    stream: str = ""
    sequence: int = 0
    consumer_sequence: int = 0
    timestamp: datetime | None = None
    redelivery: bool = False
    num_delivered: int = 0
    pending: int = 0
    subject: str = ""

    @classmethod
    def from_headers(cls, headers: dict[str, list[str]] | None) -> DeliveryMetadata:
        """Parse delivery metadata from NATS message headers.

        Parameters
        ----------
        headers:
            The ``nats.Msg.headers`` dict. Header keys are upper-cased by
            NATS, so this method looks up known keys case-insensitively.

        Returns
        -------
        DeliveryMetadata
            Parsed metadata; missing fields fall back to their defaults.
        """
        if not headers:
            return cls()

        def _get(key: str) -> str | None:
            # NATS uppercases header keys
            upper = key.upper()
            for k, v in headers.items():
                if k.upper() == upper:
                    return v[0] if v else None
            return None

        stream = _get("Nats-JS-Stream") or ""
        try:
            sequence = int(_get("Nats-JS-Sequence") or 0)
        except ValueError:
            sequence = 0
        try:
            consumer_seq = int(_get("Nats-Consumer-Seq") or 0)
        except ValueError:
            consumer_seq = 0
        try:
            num_delivered = int(_get("Nats-Num-Delivered") or 0)
        except ValueError:
            num_delivered = 0
        try:
            pending = int(_get("Nats-Consumer-Pending") or 0)
        except ValueError:
            pending = 0

        ts_raw = _get("Nats-JS-Time-Stamp")
        timestamp: datetime | None = None
        if ts_raw:
            try:
                timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                timestamp = None

        return cls(
            stream=stream,
            sequence=sequence,
            consumer_sequence=consumer_seq,
            timestamp=timestamp,
            redelivery=num_delivered > 1,
            num_delivered=num_delivered,
            pending=pending,
        )

    @classmethod
    def from_meta(cls, meta: Any) -> DeliveryMetadata:
        """Parse delivery metadata from a NATS ``JetStreamMetaInfo`` object.

        nats-py exposes the JetStream delivery info on ``msg.meta`` as a
        :class:`~nats.js.client.JetStreamMetaInfo` with the fields
        ``stream``, ``stream_seq``, ``consumer_seq``, ``num_delivered``,
        ``timestamp``, and ``pending``. This is the preferred source over
        parsing raw headers.

        Parameters
        ----------
        meta:
            A ``JetStreamMetaInfo`` (or any object exposing the same
            attributes). ``None`` is tolerated and yields an empty result.
        """
        if meta is None:
            return cls()
        try:
            stream = str(getattr(meta, "stream", "") or "")
            sequence = int(getattr(meta, "stream_seq", 0) or 0)
            consumer_sequence = int(getattr(meta, "consumer_seq", 0) or 0)
            num_delivered = int(getattr(meta, "num_delivered", 0) or 0)
            pending = int(getattr(meta, "pending", 0) or 0)
        except (TypeError, ValueError):
            return cls()

        timestamp = getattr(meta, "timestamp", None)
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = None

        return cls(
            stream=stream,
            sequence=sequence,
            consumer_sequence=consumer_sequence,
            timestamp=timestamp,
            redelivery=num_delivered > 1,
            num_delivered=num_delivered,
            pending=pending,
        )


# ---------------------------------------------------------------------------
# Event envelope (wire format)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EventEnvelope:
    """The wire envelope for a single event message.

    An :class:`EventEnvelope` wraps a :class:`~schemas.events.Event` with
    delivery metadata that NATS attaches at publish time.

    Attributes
    ----------
    event:
        The canonical event record.
    subject:
        The NATS subject this envelope is being delivered on.
    published_at:
        When the publisher stamped this envelope (UTC).
    delivery:
        Delivery metadata parsed from NATS headers (may be empty for
        publish-side envelopes).
    """

    event: Event
    subject: str = ""
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivery: DeliveryMetadata = field(default_factory=DeliveryMetadata)

    def to_json(self) -> bytes:
        """Serialize the envelope to compact JSON bytes for the wire."""
        # Embed delivery metadata alongside the event for replay/debugging.
        payload = self.event.model_dump(mode="json")
        envelope = {
            **payload,
            "__delivery": {
                "subject": self.subject,
                "published_at": self.published_at.isoformat(),
                "stream": self.delivery.stream,
                "sequence": self.delivery.sequence,
            },
        }
        return json.dumps(envelope, separators=(",", ":"), default=str).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes, subject: str = "") -> EventEnvelope:
        """Deserialize an :class:`EventEnvelope` from wire bytes.

        Parameters
        ----------
        data:
            JSON-encoded envelope bytes.
        subject:
            The NATS subject the message arrived on (for metadata).

        Returns
        -------
        EventEnvelope
            The deserialized envelope.
        """
        try:
            raw = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Event envelope is not valid JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Event envelope must be an object, got {type(raw).__name__}")

        delivery_info = raw.pop("__delivery", {}) if isinstance(raw.get("__delivery"), dict) else {}

        # Reconstruct the event from the remaining keys
        event = Event.model_validate(raw)

        published_at = None
        if delivery_info.get("published_at"):
            try:
                published_at = datetime.fromisoformat(delivery_info["published_at"])
            except ValueError:
                published_at = None

        delivery = DeliveryMetadata(
            stream=delivery_info.get("stream", ""),
            sequence=int(delivery_info.get("sequence", 0)),
        )

        return cls(
            event=event,
            subject=delivery_info.get("subject", subject),
            published_at=published_at or datetime.now(timezone.utc),
            delivery=delivery,
        )


# ---------------------------------------------------------------------------
# Replay request / result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    """Parameters for a durable replay from a JetStream stream.

    Attributes
    ----------
    subject:
        NATS subject (or wildcard) to replay.
    start_sequence:
        Inclusive stream sequence to begin from (``1`` for the oldest).
    end_sequence:
        Exclusive stream sequence to stop at (``0`` for no limit).
    limit:
        Maximum number of messages to return.
    subject_filter:
        Optional wildcard filter to apply during replay (e.g.
        ``nervcenter.task.*``).
    """

    subject: str
    start_sequence: int = 1
    end_sequence: int = 0
    limit: int = 100
    subject_filter: str | None = None


@dataclass(slots=True)
class ReplayResult:
    """Result of a replay operation.

    Attributes
    ----------
    events:
        The list of decoded events, in stream order.
    total_delivered:
        Number of messages delivered (may be less than ``len(events)`` if
        some were dropped as invalid).
    total_dropped:
        Number of messages that failed to decode/validate.
    start_sequence:
        The stream sequence of the first delivered message.
    end_sequence:
        The stream sequence of the last delivered message.
    truncated:
        ``True`` if the replay stopped because the limit was hit.
    """

    events: list[Event] = field(default_factory=list)
    total_delivered: int = 0
    total_dropped: int = 0
    start_sequence: int = 0
    end_sequence: int = 0
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return len(self.events) == 0


# ---------------------------------------------------------------------------
# Wire encode / decode helpers
# ---------------------------------------------------------------------------


def encode_event(event: Event, subject: str = "") -> bytes:
    """Encode an :class:`Event` into the wire envelope bytes.

    Convenience wrapper around :meth:`EventEnvelope.to_json` for the
    publisher.
    """
    envelope = EventEnvelope(event=event, subject=subject)
    return envelope.to_json()


def decode_event(data: bytes, subject: str = "") -> Event:
    """Decode wire bytes into a canonical :class:`Event`.

    Convenience wrapper around :meth:`EventEnvelope.from_json` for the
    subscriber.  Returns only the event; use :meth:`EventEnvelope.from_json`
    directly when delivery metadata is needed.
    """
    return EventEnvelope.from_json(data, subject=subject).event


__all__ = [
    "EventEnvelope",
    "DeliveryMetadata",
    "ReplayRequest",
    "ReplayResult",
    "encode_event",
    "decode_event",
    "generate_correlation_id",
    "new_trace_id",
]
