"""Event bus: subscriptions, dispatch, and replay.

This package implements the NATS JetStream event ingestion pipeline that
backs NerveCenter:

- :mod:`~backend.events.nats_client` — NATS / JetStream connection
  configuration and lifecycle (:class:`NatsClient`, :class:`NATSConfig`).
- :mod:`~backend.events.models` — wire envelope and replay models
  (:class:`EventEnvelope`, :class:`ReplayRequest`, :class:`ReplayResult`).
- :mod:`~backend.events.validators` — event validation middleware
  (:class:`EventValidator`, :class:`ValidationResult`).
- :mod:`~backend.events.publisher` — :class:`EventPublisher` for sending
  events to NATS.
- :mod:`~backend.events.subscriber` — :class:`EventSubscriber` for
  consuming events.
- :mod:`~backend.events.processor` — :class:`EventStorageProcessor` (writes
  validated events to PostgreSQL) and :class:`EventReplay` (durable replay).

Typical wiring::

    from backend.persistence import create_persistence, config_from_env
    from backend.events import (
        EventPublisher,
        EventSubscriber,
        EventStorageProcessor,
        EventReplay,
        EventValidator,
        NatsClient,
        config_from_env as nats_config,
    )

    db_engine, session_factory = create_persistence()
    nats = NatsClient(nats_config())
    await nats.connect()
    await nats.ensure_stream()

    validator = EventValidator()
    publisher = EventPublisher(nats)
    storage = EventStorageProcessor(session_factory, validator=validator)
    subscriber = EventSubscriber(nats, validator=validator)
    subscriber.register_handler("task.*", storage.handle_event)
    await subscriber.start()
"""

from .models import (
    DeliveryMetadata,
    EventEnvelope,
    ReplayRequest,
    ReplayResult,
    decode_event,
    encode_event,
    generate_correlation_id,
)
from .nats_client import NatsClient, NATSConfig, config_from_env
from .processor import EventReplay, EventStorageProcessor
from .publisher import EventPublisher, PublishResult
from .subscriber import EventHandler, EventSubscriber, SubscriptionConfig
from .validators import (
    EventValidator,
    PayloadValidatorRegistry,
    ValidationResult,
    validate_event,
    validate_structural,
)

__all__ = [
    # nats_client
    "NATSConfig",
    "NatsClient",
    "config_from_env",
    # models
    "EventEnvelope",
    "DeliveryMetadata",
    "ReplayRequest",
    "ReplayResult",
    "encode_event",
    "decode_event",
    "generate_correlation_id",
    # validators
    "EventValidator",
    "ValidationResult",
    "PayloadValidatorRegistry",
    "validate_event",
    "validate_structural",
    # publisher
    "EventPublisher",
    "PublishResult",
    # subscriber
    "EventSubscriber",
    "EventHandler",
    "SubscriptionConfig",
    # processor
    "EventStorageProcessor",
    "EventReplay",
]
