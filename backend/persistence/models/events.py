"""Event ORM model mapping :class:`~schemas.events.Event`.

This table stores every event emitted on the NerveCenter event bus as a
persisted record. The schema mirrors the Pydantic :class:`~schemas.events.Event`
contract (Section 10 of the specification).

Table columns
-------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``event_type`` (text) — machine-readable event type (e.g. ``entity.created``).
- ``category`` (text) — subsystem classification (one of the :data:`EventCategory`
  literals).
- ``occurred_at`` (timestamp) — when the underlying phenomenon occurred.
- ``source`` (text) — origin of the event (connector id, agent id, ``internal``).
- ``subject`` (UUID text, nullable) — primary subject id the event is about.
- ``payload`` (JSONB) — type-specific event body.
- ``severity`` (text) — operational severity (debug|info|warning|error|critical).
- ``trace_id`` / ``correlation_id`` / ``parent_event_id`` (UUID text, nullable) —
  tracing lineage.
- ``stream`` / ``sequence`` (text/int, nullable) — durable replay position.
- ``idempotency_key`` (text, nullable) — deduplication key.

Indexes
-------
- ``ix_events_event_type`` — fast filtering by event type.
- ``ix_events_category`` — subsystem-level queries.
- ``ix_events_source`` — origin tracking.
- ``ix_events_occurred_at`` — time-range queries.
- ``ix_events_subject`` — entity-centric event history.
- ``ix_events_stream_sequence`` — WAL replay ordering.

Vector support
--------------
Optional ``embedding`` column (pgvector) for semantic search over event content.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Event(Base):
    """ORM mapping of :class:`~schemas.events.Event`."""

    __tablename__ = "events"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime]
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        Jsonb, default=dict, nullable=False
    )
    severity: Mapped[str] = mapped_column(String(16), default="info")
    trace_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    parent_event_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), nullable=True, index=True
    )
    stream: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    # Optional embedding for semantic search (pgvector)
    embedding: Mapped[list[float] | None] = mapped_column(
        "embedding", BigInteger, nullable=True
    )

    __table_args__ = (
        Index(
            "ix_events_occurred_at",
            text("occurred_at DESC"),
        ),
        Index(
            "ix_events_subject_occurred_at",
            "subject",
            text("occurred_at DESC"),
        ),
        Index(
            "ix_events_stream_sequence",
            "stream",
            "sequence",
            "occurred_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Event id={self.id!r} type={self.event_type!r} "
            f"source={self.source!r} occurred_at={self.occurred_at}>"
        )
