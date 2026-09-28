"""Event storage processor and replay for the NerveCenter event bus.

This module provides:

- :class:`EventStorageProcessor` — persists validated events to PostgreSQL
  via the SQLAlchemy ORM model, deduplicates by ``idempotency_key``, and
  verifies event integrity via SHA-256 hash before storage.
- :class:`EventReplay` — durable replay of events from a JetStream stream,
  supporting sequence ranges, subject filters, and limits.

The storage processor is designed to be registered as a handler on the
:class:`~backend.events.subscriber.EventSubscriber`, or used standalone
with a direct event feed.

Usage (as a subscriber handler)::

    storage = EventStorageProcessor(session_factory)
    subscriber.register_handler("*", storage.handle_event)

Usage (replay)::

    replay = EventReplay(nats_client, config)
    result = await replay.replay(ReplayRequest(subject="nervcenter.task.*", limit=50))
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schemas.events import Event

from .models import DeliveryMetadata, ReplayRequest, ReplayResult, decode_event
from .nats_client import NATSConfig, NatsClient
from .validators import EventValidator

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# EventStorageProcessor
# ---------------------------------------------------------------------------


class EventStorageProcessor:
    """Persists validated events to PostgreSQL.

    Acts as the final stage of the event ingestion pipeline:

    1. Verify event integrity (SHA-256 hash).
    2. Deduplicate via ``idempotency_key`` (upsert semantics).
    3. Write the event to the ``events`` table.
    4. Log the correlation metadata for observability.

    Parameters
    ----------
    session_factory:
        An :class:`async_sessionmaker` bound to the PostgreSQL engine.
    validator:
        Optional :class:`EventValidator` for re-validation before storage.
        Defaults to a shared :class:`EventValidator`.
    enforce_integrity:
        When ``True`` (default), events with a mismatching hash are rejected.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        validator: EventValidator | None = None,
        enforce_integrity: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._validator = validator or EventValidator()
        self._enforce_integrity = enforce_integrity

    # -- handler entry point ----------------------------------------------------

    async def handle_event(
        self,
        event: Event,
        delivery: DeliveryMetadata,
    ) -> None:
        """Process and store a single event.

        This method is the handler registered on the subscriber. It:

        1. Validates integrity.
        2. Attempts to store the event (upsert on ``idempotency_key``).
        3. Logs the outcome.

        Raises
        ------
        ValueError
            If the event fails integrity verification (and enforcement is on).
        """
        # --- integrity check ---
        if self._enforce_integrity and not self._verify_integrity(event):
            raise ValueError(
                f"Event {event.id} failed integrity verification: "
                f"stored hash {event.hash!r} != computed {event.fingerprint()!r}"
            )

        # --- store ---
        result = await self._store_event(event, delivery)
        log.info(
            "events.stored",
            event_id=event.id,
            event_type=event.event_type,
            correlation_id=event.correlation_id,
            trace_id=event.trace_id,
            stored=result,
        )

    # -- bulk handler -----------------------------------------------------------

    async def handle_event_batch(self, events: list[Event]) -> int:
        """Store a batch of events in a single transaction.

        Returns the number of events successfully stored (new + updated).
        """
        stored = 0
        async with self._session_factory() as session:
            try:
                for event in events:
                    if self._enforce_integrity and not self._verify_integrity(event):
                        log.warning(
                            "events.integrity_skip",
                            event_id=event.id,
                            event_type=event.event_type,
                        )
                        continue
                    orm_event = self._to_orm(event)
                    session.add(orm_event)
                    stored += 1
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return stored

    # -- storage ------------------------------------------------------------------

    async def _store_event(
        self, event: Event, delivery: DeliveryMetadata
    ) -> bool:
        """Store a single event, using upsert for idempotency.

        Returns
        -------
        bool
            ``True`` if the event was inserted or updated, ``False`` if it
            was a no-op (e.g. already present with same content).
        """
        # Lazy import to avoid circular dependency at module load
        from backend.persistence.models.events import Event as EventORM

        orm_event = self._to_orm(event, delivery=delivery)

        async with self._session_factory() as session:
            try:
                # Check for existing event by idempotency key or id
                existing = None
                if event.idempotency_key:
                    stmt = select(EventORM).where(
                        EventORM.idempotency_key == event.idempotency_key
                    )
                    existing = (await session.execute(stmt)).scalar_one_or_none()

                if existing is not None:
                    # Update if content changed
                    if existing.hash != event.hash:
                        self._update_orm(existing, event, delivery=delivery)
                        await session.commit()
                        log.info("events.updated", event_id=event.id)
                        return True
                    else:
                        log.debug("events.duplicate_skipped", event_id=event.id)
                        return False

                # Insert new
                session.add(orm_event)
                await session.commit()
                log.debug("events.inserted", event_id=event.id)
                return True

            except Exception:
                await session.rollback()
                raise

    def _to_orm(
        self,
        event: Event,
        delivery: DeliveryMetadata | None = None,
    ) -> Any:
        """Convert a Pydantic :class:`Event` to the SQLAlchemy ORM model.

        Returns an ORM instance (type-annotated as ``Any`` to avoid circular
        import at module level).
        """
        from backend.persistence.models.events import Event as EventORM

        # stream/sequence: prefer delivery metadata if available
        stream = event.stream
        sequence = event.sequence
        if delivery is not None:
            if delivery.stream and not stream:
                stream = delivery.stream
            if delivery.sequence and not sequence:
                sequence = delivery.sequence

        return EventORM(
            id=event.id,
            created_at=event.created_at,
            schema_version=event.schema_version,
            hash=event.hash,
            event_type=event.event_type,
            category=event.category,
            occurred_at=event.occurred_at,
            source=event.source,
            subject=event.subject,
            payload=event.payload,
            severity=event.severity,
            trace_id=event.trace_id,
            correlation_id=event.correlation_id,
            parent_event_id=event.parent_event_id,
            stream=stream,
            sequence=sequence,
            idempotency_key=event.idempotency_key,
        )

    @staticmethod
    def _update_orm(orm: Any, event: Event, delivery: DeliveryMetadata | None = None) -> None:
        """Update an existing ORM row with new event data."""
        orm.hash = event.hash
        orm.payload = event.payload
        if delivery is not None:
            if delivery.stream:
                orm.stream = delivery.stream
            if delivery.sequence:
                orm.sequence = delivery.sequence

    # -- integrity -----------------------------------------------------------------

    def _verify_integrity(self, event: Event) -> bool:
        """Check the event's integrity hash.

        Returns ``True`` when the hash matches or no hash is stored.
        Returns ``False`` when a hash is present but does not match.
        """
        return event.verify_integrity()

    # -- queries -------------------------------------------------------------------

    async def query_by_correlation(self, correlation_id: str) -> list[Event]:
        """Return all events sharing a given correlation ID, in stream order.

        Useful for tracing a logical unit of work through the system.
        """
        from backend.persistence.models.events import Event as EventORM

        async with self._session_factory() as session:
            stmt = (
                select(EventORM)
                .where(EventORM.correlation_id == correlation_id)
                .order_by(EventORM.occurred_at)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return [self._orm_to_pydantic(r) for r in rows]

    async def query_by_subject(
        self,
        subject_id: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Return events for a given subject (entity ID), most recent first.

        Parameters
        ----------
        subject_id:
            The UUID string of the subject entity.
        since:
            Only include events after this timestamp.
        limit:
            Maximum number of events to return.
        """
        from backend.persistence.models.events import Event as EventORM

        async with self._session_factory() as session:
            stmt = select(EventORM).where(EventORM.subject == subject_id)
            if since is not None:
                stmt = stmt.where(EventORM.occurred_at >= since)
            stmt = stmt.order_by(EventORM.occurred_at.desc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._orm_to_pydantic(r) for r in rows]

    async def query_by_type(
        self,
        event_type: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Return events of a given type within a time range."""
        from backend.persistence.models.events import Event as EventORM

        async with self._session_factory() as session:
            stmt = select(EventORM).where(EventORM.event_type == event_type)
            if since is not None:
                stmt = stmt.where(EventORM.occurred_at >= since)
            if until is not None:
                stmt = stmt.where(EventORM.occurred_at <= until)
            stmt = stmt.order_by(EventORM.occurred_at.asc()).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._orm_to_pydantic(r) for r in rows]

    @staticmethod
    def _orm_to_pydantic(orm: Any) -> Event:
        """Convert an ORM event row back to a Pydantic :class:`Event`."""
        return Event(
            id=orm.id,
            created_at=orm.created_at,
            schema_version=orm.schema_version,
            hash=orm.hash,
            event_type=orm.event_type,
            category=orm.category,
            occurred_at=orm.occurred_at,
            source=orm.source,
            subject=orm.subject,
            payload=orm.payload,
            severity=orm.severity,
            trace_id=orm.trace_id,
            correlation_id=orm.correlation_id,
            parent_event_id=orm.parent_event_id,
            stream=orm.stream,
            sequence=orm.sequence,
            idempotency_key=orm.idempotency_key,
        )


# ---------------------------------------------------------------------------
# EventReplay
# ---------------------------------------------------------------------------


class EventReplay:
    """Durable replay of events from a JetStream stream.

    Supports replaying events by stream sequence range, subject filter,
    and count limit. The replay uses the JetStream ``Consumer`` API to
    iterate messages in order.

    Parameters
    ----------
    nats_client:
        A connected :class:`NatsClient` instance.
    config:
        The :class:`NATSConfig`.
    validator:
        Optional :class:`EventValidator` applied to replayed events.
    """

    def __init__(
        self,
        nats_client: NatsClient,
        config: NATSConfig | None = None,
        *,
        validator: EventValidator | None = None,
    ) -> None:
        self._nats = nats_client
        self._config = config or nats_client.config
        self._validator = validator or EventValidator()

    async def replay(self, request: ReplayRequest) -> ReplayResult:
        """Replay events from the JetStream stream.

        Parameters
        ----------
        request:
            The :class:`ReplayRequest` describing the range, subject,
            and limit.

        Returns
        -------
        ReplayResult
            The decoded events in stream order.
        """
        js = self._nats.jetstream
        result = ReplayResult()
        consumer = None
        truncated = False

        try:
            # Create a temporary consumer for replay
            consumer_name = f"replay-{datetime.now(timezone.utc).isoformat()}"
            consumer = js.get_consumer(
                self._config.stream_name,
                consumer_name,
            )

            # Determine start sequence
            start_seq = request.start_sequence

            # Fetch messages
            delivered = 0
            truncated = False
            while delivered < request.limit:
                remaining = request.limit - delivered

                # End sequence check
                if request.end_sequence > 0 and start_seq >= request.end_sequence:
                    break

                msgs = await consumer.fetch(remaining, next_timeout=5.0)
                if not msgs:
                    break

                for msg in msgs:
                    seq = getattr(msg, "sequence", 0)
                    if request.end_sequence > 0 and seq >= request.end_sequence:
                        truncated = True
                        break

                    subject = getattr(msg, "subject", "")
                    # Apply subject filter
                    if request.subject_filter:
                        if not _match_subject_filter(subject, request.subject_filter):
                            continue

                    try:
                        event = decode_event(msg.data, subject=subject)
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "events.replay_decode_failed",
                            subject=subject,
                            sequence=seq,
                            error=str(exc),
                        )
                        result.total_dropped += 1
                        continue

                    # Validate if validator is configured
                    if self._validator is not None:
                        try:
                            validation = self._validator.validate(event.model_dump(mode="json"))
                            if not validation.valid:
                                log.warning(
                                    "events.replay_invalid",
                                    event_id=event.id,
                                    errors=validation.errors,
                                )
                                result.total_dropped += 1
                                continue
                        except Exception:  # noqa: BLE001
                            pass

                    # Track sequence range
                    if result.start_sequence == 0:
                        result.start_sequence = seq
                    result.end_sequence = seq

                    result.events.append(event)
                    result.total_delivered += 1
                    delivered += 1

                # Clean up message ack
                for msg in msgs:
                    try:
                        await msg.ack()
                    except Exception:  # noqa: BLE001
                        pass

                if truncated:
                    break

        except Exception as exc:  # noqa: BLE001
            log.error("events.replay_failed", error=str(exc))
        finally:
            # Delete the temporary consumer
            if consumer is not None:
                try:
                    await consumer.delete()
                except Exception:  # noqa: BLE001
                    pass

        result.truncated = truncated
        log.info(
            "events.replay_complete",
            delivered=result.total_delivered,
            dropped=result.total_dropped,
            truncated=result.truncated,
            start_seq=result.start_sequence,
            end_seq=result.end_sequence,
        )
        return result

    async def replay_by_correlation(
        self,
        correlation_id: str,
        *,
        limit: int = 100,
    ) -> list[Event]:
        """Replay all events sharing a correlation ID from the stream.

        This is a convenience wrapper that replays the full stream and
        filters by correlation ID. For very large streams, prefer querying
        the PostgreSQL storage directly via
        :meth:`EventStorageProcessor.query_by_correlation`.

        Parameters
        ----------
        correlation_id:
            The correlation ID to filter by.
        limit:
            Maximum number of events to return.

        Returns
        -------
        list[Event]
            Events matching the correlation, in stream order.
        """
        request = ReplayRequest(
            subject=self._config.events_subject,
            start_sequence=1,
            limit=limit,
        )
        result = await self.replay(request)
        return [e for e in result.events if e.correlation_id == correlation_id][:limit]


# ---------------------------------------------------------------------------
# Subject filter helper
# ---------------------------------------------------------------------------


def _match_subject_filter(subject: str, filter_pattern: str) -> bool:
    """Check if a subject matches a NATS subject filter (wildcard support).

    Supports:
    - ``*`` — matches a single token (e.g. ``nervcenter.task.*``).
    - ``>`` — matches one or more tokens (e.g. ``nervcenter.>``).

    Parameters
    ----------
    subject:
        The actual subject.
    filter_pattern:
        The filter pattern (NATS subject syntax).

    Returns
    -------
    bool
    """
    if filter_pattern == subject:
        return True

    # Convert NATS subject pattern to regex
    tokens_pattern = filter_pattern.split(".")
    tokens_subject = subject.split(".")

    if len(tokens_pattern) == 1 and tokens_pattern[0] == ">":
        return True

    for i, pt in enumerate(tokens_pattern):
        if pt == ">":
            # > matches all remaining tokens
            return True
        if i >= len(tokens_subject):
            return False
        if pt == "*":
            continue
        if pt != tokens_subject[i]:
            return False

    return len(tokens_pattern) == len(tokens_subject)


__all__ = ["EventStorageProcessor", "EventReplay"]
