"""Event subscriber for the NerveCenter NATS JetStream event bus.

This module provides :class:`EventSubscriber`, the primary interface for
consuming events from the NATS JetStream event stream. It handles:

- Creating JetStream pull subscriptions with acknowledgment.
- Validating consumed events via the :class:`EventValidator` middleware.
- Invoking registered :class:`EventHandler` callables for each valid event.
- Supporting durable replay from a stream position (via :mod:`backend.events.processor`).
- Correlation ID propagation: subscribers extract the ``correlation_id``
  and ``trace_id`` from each event so handlers can thread them into
  downstream work.

Usage::

    subscriber = EventSubscriber(nats_client, config, validator=EventValidator())
    subscriber.register_handler("task.completed", my_task_handler)
    await subscriber.start()
    # … later …
    await subscriber.stop()
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

import structlog

from schemas.events import Event

from .models import DeliveryMetadata, EventEnvelope
from .nats_client import NatsClient, NATSConfig
from .validators import EventValidator

log = structlog.get_logger(__name__)

# A handler receives (event, delivery_metadata) and returns an awaitable.
EventHandler = Callable[["Event", "DeliveryMetadata"], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Subscription descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SubscriptionConfig:
    """Configuration for a JetStream pull subscription.

    Attributes
    ----------
    subject:
        The NATS subject (or wildcard) to subscribe to.
    consumer_name:
        Durable consumer name.
    stream:
        JetStream stream name (optional; NATS infers from the subject).
    inbox_prefix:
        Subject prefix for the consumer inbox.
    ack_wait:
        Seconds before a message is considered un-acknowledged (redelivered).
    max_ack:
        Maximum redeliveries before the message is marked failed.
    """

    subject: str = ""
    consumer_name: str = "nervcenter-subscriber"
    stream: str | None = None
    inbox_prefix: str = ""
    ack_wait: int = 30
    max_ack: int = 3


# ---------------------------------------------------------------------------
# EventSubscriber
# ---------------------------------------------------------------------------


class EventSubscriber:
    """Consumes events from the NATS JetStream event stream.

    The subscriber uses a JetStream **pull subscription** with a durable
    consumer so that messages are delivered at-least-once and acknowledgments
    control redelivery. The main consumption loop runs in a background
    :class:`asyncio.Task`.

    Parameters
    ----------
    nats_client:
        A connected :class:`NatsClient` instance.
    config:
        The :class:`NATSConfig`; provides the subject prefix and stream.
    validator:
        The :class:`EventValidator` used to gate incoming events.
    ack_wait:
        Acknowledgment wait in seconds.
    max_ack:
        Max redeliveries before a message is dead-lettered.
    """

    def __init__(
        self,
        nats_client: NatsClient,
        config: NATSConfig | None = None,
        *,
        validator: EventValidator | None = None,
        ack_wait: int = 30,
        max_ack: int = 3,
    ) -> None:
        self._nats = nats_client
        self._config = config or nats_client.config
        self._validator = validator or EventValidator()
        self._ack_wait = ack_wait
        self._max_ack = max_ack

        self._handlers: dict[str, list[EventHandler]] = {}
        self._consumer: Any = None  # nats.js.context.Consumer
        self._subscriber: Any = None
        self._task: asyncio.Task | None = None
        self._running = False
        self._consumer_name = f"{self._config.consumer_name}-sub"
        self._dead_letter: list[dict[str, Any]] = []

    # -- properties -----------------------------------------------------------

    @property
    def config(self) -> NATSConfig:
        return self._config

    @property
    def nats_client(self) -> NatsClient:
        return self._nats

    @property
    def validator(self) -> EventValidator:
        return self._validator

    @property
    def is_running(self) -> bool:
        return self._running

    # -- handler registration ---------------------------------------------------

    def register_handler(
        self,
        event_type_pattern: str,
        handler: EventHandler,
    ) -> None:
        """Register ``handler`` for events matching ``event_type_pattern``.

        Parameters
        ----------
        event_type_pattern:
            An event type or prefix pattern. Use ``"*"`` to match everything,
            ``"task.*"`` to match all task events, or ``"task.completed"``
            for an exact type.
        handler:
            An async callable ``(event, delivery) -> None``.
        """
        self._handlers.setdefault(event_type_pattern, []).append(handler)
        log.info(
            "events.handler_registered",
            pattern=event_type_pattern,
            handler=getattr(handler, "__name__", str(handler)),
        )

    def _resolve_handlers(self, event: Event) -> list[EventHandler]:
        """Return the handlers applicable to a given event.

        Matching strategy (first match wins at the *pattern* level, but all
        registered handlers under a matching pattern are invoked):

        1. Exact match on ``event_type``.
        2. Prefix match on ``event_type`` (supports ``"task.*"`` style).
        3. Wildcard ``"*"``.
        """
        handlers: list[EventHandler] = []
        et = event.event_type

        # Exact
        if et in self._handlers:
            handlers.extend(self._handlers[et])

        # Prefix patterns (e.g. "task.*" matches "task.completed")
        for pattern, hdlrs in self._handlers.items():
            if pattern == et:
                continue  # already handled
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if et.startswith(prefix):
                    for h in hdlrs:
                        if h not in handlers:
                            handlers.append(h)
            elif pattern == "*":
                for h in hdlrs:
                    if h not in handlers:
                        handlers.append(h)
            elif pattern.endswith(".*") is False and pattern.startswith(event.category):
                # category-level match
                if et.startswith(f"{event.category}."):
                    for h in hdlrs:
                        if h not in handlers:
                            handlers.append(h)

        return handlers

    # -- lifecycle -------------------------------------------------------------

    async def start(self) -> None:
        """Start the background consumption loop.

        Creates the JetStream pull consumer (idempotently) and launches the
        subscribe loop as an :class:`asyncio.Task`.
        """
        if self._running:
            log.warning("events.subscriber_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("events.subscriber_started", consumer=self._consumer_name)

    async def stop(self) -> None:
        """Stop the consumption loop and close the subscription."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass
            self._task = None

        # The pull subscription is abandoned when the task is cancelled;
        # nats-py's PullSubscription has no explicit close() method, so we
        # simply drop the reference. The durable consumer persists on the
        # server and retains its cursor position for the next run.
        self._subscriber = None

        log.info("events.subscriber_stopped")

    # -- consumption loop -------------------------------------------------------

    async def _run_loop(self) -> None:
        """Run the main subscribe loop until :meth:`stop` is called.

        Uses the JetStream pull-subscription API (``pull_subscribe`` +
        ``fetch``), which is the documented consumption pattern in nats-py.
        """
        try:
            js = self._nats.jetstream
            subject = self._config.events_subject

            # Ensure the durable consumer exists up front so that ack_wait /
            # max_ack are set on the server (pull_subscribe alone cannot
            # configure them). Idempotent on subsequent starts.
            try:
                await js.consumer_info(self._config.stream_name, self._consumer_name)
            except Exception:
                await js.add_consumer(
                    self._config.stream_name,
                    durable=self._consumer_name,
                    config=ConsumerConfig(
                        durable=self._consumer_name,
                        ack_wait=self._ack_wait,
                        max_ack=self._max_ack,
                    ),
                )

            # Create the pull subscription bound to the durable consumer.
            self._subscriber = await js.pull_subscribe(
                subject,
                durable=self._consumer_name,
                durables={
                    self._consumer_name: {
                        "stream": self._config.stream_name,
                        "max_ack": self._max_ack,
                    }
                },
            )

            log.info(
                "events.subscriber_subscribed",
                subject=subject,
                stream=self._config.stream_name,
                consumer=self._consumer_name,
            )

            while self._running:
                try:
                    msgs = await self._subscriber.fetch(1, timeout=1.0)
                except TimeoutError:
                    # No messages within the window; loop again so that
                    # ``stop()`` can be observed promptly.
                    continue
                except Exception:
                    # Transport hiccup during an idle wait; retry on the next
                    # iteration (allow_reconnect handles the reconnect).
                    await asyncio.sleep(0.5)
                    continue
                if msgs:
                    for msg in msgs:
                        await self._process_message(msg)

        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            log.error("events.subscriber_loop_error", error=str(exc))
            self._running = False
            raise

    async def _process_message(self, msg: Any) -> None:
        """Process a single NATS message through validation + handlers.

        Parameters
        ----------
        msg:
            An ``nats.js.Msg`` (or compatible) with ``.data`` (bytes),
            ``.headers`` (dict), and — for JetStream messages — ``.meta``
            (a :class:`~nats.js.client.JetStreamMetaInfo`).
        """
        # Prefer the JetStream meta object (clean fields) over raw headers.
        meta = getattr(msg, "meta", None)
        if meta is not None:
            delivery = DeliveryMetadata.from_meta(meta)
        else:
            delivery = DeliveryMetadata.from_headers(getattr(msg, "headers", None))

        # Decode the event envelope
        try:
            envelope = EventEnvelope.from_json(msg.data, subject=getattr(msg, "subject", ""))
        except (ValueError, Exception) as exc:  # noqa: BLE001
            log.error(
                "events.decode_failed",
                subject=getattr(msg, "subject", ""),
                error=str(exc),
            )
            self._dead_letter.append({"subject": getattr(msg, "subject", ""), "error": str(exc)})
            # Ack to avoid redelivery of undecodable messages
            try:
                await msg.ack()
            except Exception:  # noqa: BLE001
                pass
            return

        event = envelope.event

        # Propagate correlation metadata for handler context
        correlation_id = event.correlation_id
        trace_id = event.trace_id
        log.debug(
            "events.received",
            event_id=event.id,
            event_type=event.event_type,
            correlation_id=correlation_id,
            trace_id=trace_id,
            stream=delivery.stream,
            sequence=delivery.sequence,
        )

        # --- validate ---
        result = self._validator.validate(event.model_dump(mode="json"))
        if not result.valid:
            log.warning(
                "events.validation_failed",
                event_id=event.id,
                event_type=event.event_type,
                errors=result.errors,
            )
            # Ack invalid events to avoid poison-pill redelivery
            try:
                await msg.ack()
            except Exception:  # noqa: BLE001
                pass
            return

        # --- dispatch to handlers ---
        handlers = self._resolve_handlers(event)
        errors: list[str] = []

        for handler in handlers:
            try:
                await handler(event, delivery)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{getattr(handler, '__name__', 'handler')}: {exc}")
                log.exception(
                    "events.handler_error",
                    event_id=event.id,
                    event_type=event.event_type,
                    handler=getattr(handler, "__name__", "unknown"),
                    error=str(exc),
                )

        if errors:
            # Nack to redeliver: one handler failure should not lose the event
            try:
                await msg.nak()
            except Exception:  # noqa: BLE001
                # Best-effort: ack if nack fails
                try:
                    await msg.ack()
                except Exception:  # noqa: BLE001
                    pass
        else:
            try:
                await msg.ack()
            except Exception:  # noqa: BLE001
                pass

    # -- health -------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Return a structured health report for the subscriber."""
        report: dict[str, Any] = {
            "running": self._running,
            "task_alive": self._task is not None and not self._task.done(),
            "dead_letter_count": len(self._dead_letter),
        }
        if self._task is not None and self._task.done() and self._running:
            exc = self._task.exception()
            if exc is not None:
                report["error"] = str(exc)
        return report


__all__ = ["EventSubscriber", "SubscriptionConfig", "EventHandler"]
