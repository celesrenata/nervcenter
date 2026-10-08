"""Event publisher for the NerveCenter NATS JetStream event bus.

This module provides :class:`EventPublisher`, the primary interface for
publishing events onto the NATS JetStream event stream. It handles:

- Encoding events into the wire envelope (JSON).
- Computing and embedding the SHA-256 integrity hash.
- Propagating correlation ID and trace ID to downstream events.
- Publishing to the appropriate NATS subject via JetStream.
- Returning a :class:`PublishResult` with the stream sequence and
  acknowledgment details.

Usage::

    publisher = EventPublisher(nats_client, config)
    await publisher.publish(event)
    await publisher.publish_many(events)
    await publisher.publish_with_correlation(event, correlation_id="...")
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from schemas.events import Event

from .models import encode_event, generate_correlation_id
from .nats_client import NatsClient, NATSConfig

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Publish result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Result of a single publish operation.

    Attributes
    ----------
    success:
        ``True`` when the event was acknowledged by JetStream.
    event_id:
        The ID of the published event.
    subject:
        The NATS subject the event was published to.
    stream:
        The JetStream stream name.
    sequence:
        The stream sequence number assigned by JetStream (0 if unknown).
    published_at:
        Timestamp of the publish operation (UTC).
    error:
        Error message when the publish failed (``None`` on success).
    """

    success: bool
    event_id: str
    subject: str = ""
    stream: str = ""
    sequence: int = 0
    published_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


# ---------------------------------------------------------------------------
# EventPublisher
# ---------------------------------------------------------------------------


class EventPublisher:
    """Publishes events onto the NATS JetStream event bus.

    Parameters
    ----------
    nats_client:
        A connected :class:`NatsClient` instance.
    config:
        The :class:`NATSConfig` used for subject construction. Defaults to
        the client's configuration.
    auto_fingerprint:
        When ``True`` (default), the publisher computes and assigns the
        SHA-256 integrity hash before publishing. Set ``False`` for
        producers that manage their own fingerprinting.
    auto_correlation:
        When ``True`` (default), a new correlation ID is generated if the
        event does not already carry one.
    """

    def __init__(
        self,
        nats_client: NatsClient,
        config: NATSConfig | None = None,
        *,
        auto_fingerprint: bool = True,
        auto_correlation: bool = True,
    ) -> None:
        self._nats = nats_client
        self._config = config or nats_client.config
        self._auto_fingerprint = auto_fingerprint
        self._auto_correlation = auto_correlation

    # -- properties -----------------------------------------------------------

    @property
    def config(self) -> NATSConfig:
        """Return the active NATS configuration."""
        return self._config

    @property
    def nats_client(self) -> NatsClient:
        """Return the underlying NATS client."""
        return self._nats

    # -- publish ----------------------------------------------------------------

    async def publish(
        self,
        event: Event,
        *,
        subject: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> PublishResult:
        """Publish a single event to the NATS JetStream event bus.

        Parameters
        ----------
        event:
            The canonical event to publish.
        subject:
            Override the NATS subject (normally derived from
            ``config.subject_for_event(event.category, event.event_type)``).
        correlation_id:
            Force a specific correlation ID (overrides event's value).
        trace_id:
            Force a specific trace ID (overrides event's value).
        headers:
            Optional additional NATS headers to attach.

        Returns
        -------
        PublishResult
            With stream sequence and acknowledgment info.
        """
        # --- prepare the event (fingerprint, correlation) ---
        prepared = self._prepare_event(event, correlation_id=correlation_id, trace_id=trace_id)

        # --- determine subject ---
        if subject is None:
            subject = self._config.subject_for_event(prepared.category, prepared.event_type)

        # --- encode to wire bytes ---
        payload = encode_event(prepared, subject=subject)

        # --- publish via JetStream ---
        try:
            js = self._nats.jetstream
            ack = await js.publish(subject, payload, headers=headers)

            # Extract sequence from ack if available
            sequence = 0
            stream = ""
            if ack is not None:
                stream = getattr(ack, "stream", "") or self._config.stream_name
                sequence = getattr(ack, "sequence", 0) or 0

            log.info(
                "events.published",
                event_id=prepared.id,
                event_type=prepared.event_type,
                subject=subject,
                stream=stream,
                sequence=sequence,
                correlation_id=prepared.correlation_id,
                trace_id=prepared.trace_id,
            )

            return PublishResult(
                success=True,
                event_id=prepared.id,
                subject=subject,
                stream=stream,
                sequence=sequence,
            )

        except Exception as exc:  # noqa: BLE001
            log.error(
                "events.publish_failed",
                event_id=prepared.id,
                event_type=prepared.event_type,
                subject=subject,
                error=str(exc),
            )
            return PublishResult(
                success=False,
                event_id=prepared.id,
                subject=subject,
                error=str(exc),
            )

    async def publish_many(
        self,
        events: Sequence[Event],
        *,
        correlation_id: str | None = None,
    ) -> list[PublishResult]:
        """Publish a batch of events, optionally sharing a correlation ID.

        Parameters
        ----------
        events:
            The events to publish.
        correlation_id:
            If provided, all events share this correlation ID. If not
            provided, the first event's correlation ID (or a fresh one) is
            used for all events in the batch.

        Returns
        -------
        list[PublishResult]
            One result per event, in order.
        """
        if not events:
            return []

        results: list[PublishResult] = []
        batch_correlation = correlation_id

        for event in events:
            if batch_correlation is None:
                # Propagate the first event's correlation to the rest
                batch_correlation = (
                    event.correlation_id or self._generate_correlation()
                )
            result = await self.publish(event, correlation_id=batch_correlation)
            results.append(result)

        log.info(
            "events.batch_published",
            count=len(results),
            successes=sum(1 for r in results if r.success),
            failures=sum(1 for r in results if not r.success),
        )
        return results

    async def publish_with_correlation(
        self,
        event: Event,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> PublishResult:
        """Publish an event with explicit correlation/trace propagation.

        If no correlation ID is given, one is generated and the event's
        correlation is set. This is the recommended entry point when you
        need to ensure correlation metadata is properly propagated.
        """
        if correlation_id is None:
            correlation_id = event.correlation_id or generate_correlation_id()
        if trace_id is None:
            trace_id = event.trace_id or correlation_id

        return await self.publish(
            event,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

    # -- internal helpers --------------------------------------------------------

    def _prepare_event(
        self,
        event: Event,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> Event:
        """Return a copy of the event with fingerprint and correlation set.

        :class:`~schemas.events.Event` is frozen (spec §10), so the derived
        values are applied in a single ``model_copy(update=...)`` rather than
        by mutating the copy.
        """
        updates: dict[str, Any] = {}

        # Correlation propagation
        if correlation_id is not None:
            updates["correlation_id"] = correlation_id
        elif self._auto_correlation and event.correlation_id is None:
            updates["correlation_id"] = self._generate_correlation()

        # Trace propagation: default to correlation_id if trace is unset
        effective_trace = trace_id if trace_id is not None else event.trace_id
        if effective_trace is None:
            effective_trace = updates.get("correlation_id") or event.correlation_id
        if effective_trace is not None and effective_trace != event.trace_id:
            updates["trace_id"] = effective_trace

        # Fingerprint (must be computed after correlation/trace are fixed)
        if self._auto_fingerprint:
            staged = event.model_copy(update=updates)
            updates["hash"] = staged.fingerprint()

        if not updates:
            return event
        return event.model_copy(update=updates)

    def _generate_correlation(self) -> str:
        return str(uuid.uuid4())


__all__ = ["EventPublisher", "PublishResult"]
