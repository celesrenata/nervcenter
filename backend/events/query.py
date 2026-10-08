"""Bounded listing/query helpers for the NATS JetStream event bus.

T-H32: ``GET /api/events`` reads from the live event bus instead of
hardcoded fixtures. This module owns the read path shared by that
endpoint:

- :func:`list_events` — reads the most recent messages from the
  JetStream event stream via ``stream_info`` plus bounded ``get_msg``
  reads, and decodes them into :class:`~schemas.events.Event` records.
- :func:`find_event` — a bounded scan of recent events for one id.

Honesty contract: every bus round-trip is bounded by
:data:`BUS_READ_TIMEOUT_S`; any failure (not connected, stream missing,
timeout, read error) surfaces as :class:`EventBusError` so callers can
degrade honestly — an empty listing when the bus is *not configured*,
an error response when the bus is *configured but unreachable*.  This
module never fabricates events.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import ValidationError

from schemas.events import Event

from .models import EventEnvelope
from .nats_client import NatsClient

log = structlog.get_logger(__name__)

#: Timeout (seconds) for a single bus round-trip (``stream_info`` / ``get_msg``).
BUS_READ_TIMEOUT_S = 2.0

#: Default number of recent events the listing returns.
DEFAULT_MAX_EVENTS = 100

#: Hard upper bound on caller-requested limits.
MAX_EVENTS_LIMIT = 500


class EventBusError(RuntimeError):
    """The event bus is configured but a bounded read failed.

    Raised when the JetStream context is unavailable (client not
    connected), the event stream cannot be inspected, or a
    ``get_msg`` round-trip fails. Callers must surface this as an
    honest error — never as a fabricated listing.
    """


@dataclass(frozen=True, slots=True)
class EventQueryResult:
    """Outcome of a bounded event-bus listing read.

    Attributes
    ----------
    events:
        Decoded events in stream order (oldest first).
    total:
        Total messages in the stream at read time
        (``stream_info.state.messages``); ``0`` for an empty stream.
    scanned:
        Stream messages actually read for this request.
    stream:
        The JetStream stream name the messages came from.
    truncated:
        ``True`` when the returned list does not cover the full stream
        state — either the read window was capped by ``limit``, or some
        messages in the window could not be read or decoded. Callers
        must not present a truncated listing as complete.
    """

    events: tuple[Event, ...]
    total: int
    scanned: int
    stream: str
    truncated: bool


def _clamp_limit(limit: int) -> int:
    """Clamp a caller-supplied limit into ``[1, MAX_EVENTS_LIMIT]``."""
    return max(1, min(int(limit), MAX_EVENTS_LIMIT))


async def _roundtrip(coro: Any) -> Any:
    """Await one bus call under the global read timeout.

    Raises
    ------
    EventBusError
        When the round-trip exceeds :data:`BUS_READ_TIMEOUT_S`.
    """
    try:
        return await asyncio.wait_for(coro, timeout=BUS_READ_TIMEOUT_S)
    except TimeoutError as exc:
        raise EventBusError(
            f"event bus read timed out after {BUS_READ_TIMEOUT_S}s"
        ) from exc


def _subject_matches(subject: str, subject_prefix: str) -> bool:
    """True when ``subject`` belongs to the NerveCenter event namespace."""
    if not subject:
        return True  # no subject metadata (e.g. test doubles) → accept
    return subject == subject_prefix or subject.startswith(f"{subject_prefix}.")


async def list_events(
    nats: NatsClient,
    *,
    entity: str | None = None,
    limit: int = DEFAULT_MAX_EVENTS,
) -> EventQueryResult:
    """Read the most recent events from the JetStream event stream.

    Parameters
    ----------
    nats:
        A :class:`NatsClient` (or any object exposing the same
        ``jetstream`` / ``config`` surface — e.g. an in-memory test
        double). Must be connected.
    entity:
        Optional subject filter: only events whose ``subject`` field
        equals ``entity`` are returned (powers ``GET
        /api/events?entity=<id>``).
    limit:
        Maximum number of stream messages to read (clamped to
        ``[1, MAX_EVENTS_LIMIT]``).

    Returns
    -------
    EventQueryResult
        With events ordered oldest → newest within the scanned window.

    Raises
    ------
    EventBusError
        When the client is not connected, ``stream_info`` fails
        (stream missing or unreachable), or a read round-trip fails.
    """
    clamped = _clamp_limit(limit)

    try:
        js = nats.jetstream
    except RuntimeError as exc:
        raise EventBusError("event bus is not connected") from exc

    stream_name = nats.config.stream_name
    try:
        info = await _roundtrip(js.stream_info(stream_name))
    except EventBusError:
        raise
    except Exception as exc:  # noqa: BLE001 - any bus failure is a read failure
        raise EventBusError(f"stream_info failed for {stream_name!r}: {exc}") from exc

    state = getattr(info, "state", None)
    total = int(getattr(state, "messages", 0) or 0)
    last_seq = int(getattr(state, "last_seq", 0) or 0)
    if total <= 0 or last_seq <= 0:
        return EventQueryResult(
            events=(), total=total, scanned=0, stream=stream_name, truncated=False
        )

    count = min(total, clamped)
    subject_prefix = nats.config.subject_prefix
    events: list[Event] = []
    scanned = 0
    failures = 0
    for seq in range(last_seq - count + 1, last_seq + 1):
        try:
            msg = await _roundtrip(js.get_msg(stream_name, seq=seq))
        except EventBusError:
            raise
        except Exception as exc:  # noqa: BLE001 - stream moved under us
            log.debug("events.seq_read_failed", stream=stream_name, seq=seq, error=str(exc))
            failures += 1
            break  # return what was read so far (honest partial window)

        scanned += 1
        subject = str(getattr(msg, "subject", "") or "")
        if not _subject_matches(subject, subject_prefix):
            continue
        try:
            envelope = EventEnvelope.from_json(msg.data, subject=subject)
        except (ValueError, ValidationError) as exc:
            log.warning("events.decode_failed", stream=stream_name, seq=seq, error=str(exc))
            failures += 1
            continue

        event = envelope.event
        if entity is not None and event.subject != entity:
            continue
        events.append(event)

    return EventQueryResult(
        events=tuple(events),
        total=total,
        scanned=scanned,
        stream=stream_name,
        truncated=(total > scanned) or failures > 0,
    )


async def find_event(
    nats: NatsClient,
    event_id: str,
    *,
    limit: int = DEFAULT_MAX_EVENTS,
) -> Event | None:
    """Bounded scan of the most recent events for a single id.

    Returns
    -------
    Event | None
        The event when found within the scanned window, otherwise
        ``None`` (callers surface this as 404, not a fabricated row).
    """
    result = await list_events(nats, limit=limit)
    for event in result.events:
        if event.id == event_id:
            return event
    return None
