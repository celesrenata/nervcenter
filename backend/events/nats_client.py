"""NATS JetStream client configuration and connection management.

This module owns the *only* place in NerveCenter that constructs a NATS
connection and obtains the JetStream context. Every subsystem that needs
the event bus should depend on :class:`NatsClient` (or the
``NERVECENTER_NATS_URL`` environment variable) rather than constructing a
raw ``nats.aio.client.Client`` directly.

Key exports
-----------
- :class:`NATSConfig` — typed, frozen container of connection knobs.
- :func:`config_from_env` — build a config from process env.
- :class:`NatsClient` — async wrapper around the NATS connection and
  JetStream context with lifecycle management.

Environment variables
---------------------
- ``NERVECENTER_NATS_URL`` — NATS server URL (default ``nats://localhost:4222``).
- ``NERVECENTER_NATS_SUBJECT_PREFIX`` — subject prefix (default ``nervcenter``).
- ``NERVECENTER_NATS_STREAM_NAME`` — JetStream stream name
  (default ``NERVECENTER_EVENTS``).
- ``NERVECENTER_NATS_MAX_MSG_SIZE`` — maximum message size in bytes.
- ``NERVECENTER_NATS_RECONNECT_WAIT_MS`` — milliseconds between reconnect
  attempts.
- ``NERVECENTER_NATS_MAX_RECONNECTS`` — reconnect attempts before giving up.
- ``NERVECENTER_NATS_CONSUMER_NAME`` — default durable consumer name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog

try:
    import nats
    from nats.aio.client import Client as NatsConnection
    from nats.js import api
    from nats.js.api import ConsumerConfig
    from nats.js.client import JetStreamContext
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "nats-py is required for the event bus. Install it with: "
        "pip install nats-py"
    ) from _exc

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Environment variable names and defaults
# ---------------------------------------------------------------------------

#: Environment variable that overrides the NATS server URL when set.
ENV_NATS_URL = "NERVECENTER_NATS_URL"

#: Fallback used when ``ENV_NATS_URL`` is not set.
DEFAULT_NATS_URL = "nats://localhost:4222"

#: Default subject prefix for all NerveCenter events.
DEFAULT_SUBJECT_PREFIX = "nervcenter"

#: Default JetStream stream name.
DEFAULT_STREAM_NAME = "NERVECENTER_EVENTS"

#: Default maximum message size (1 MiB).
DEFAULT_MAX_MSG_SIZE = 1_048_576

#: Default reconnect wait in milliseconds.
DEFAULT_RECONNECT_WAIT_MS = 2_000

#: Default number of reconnect attempts before giving up.
DEFAULT_MAX_RECONNECTS = 30

#: Default JetStream consumer name for pull subscriptions.
DEFAULT_CONSUMER_NAME = "nervcenter-consumer"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NATSConfig:
    """Immutable container of NATS / JetStream connection configuration.

    Attributes
    ----------
    url:
        The NATS server URL (e.g. ``nats://localhost:4222``).
    subject_prefix:
        Prefix for all NerveCenter subjects. Events are published to
        ``{subject_prefix}.{category}.{event_type}``.
    stream_name:
        JetStream stream name for the event log.
    max_msg_size:
        Maximum allowed message size in bytes.
    reconnect_wait_ms:
        Wait between reconnect attempts (milliseconds).
    max_reconnects:
        Maximum number of reconnect attempts before giving up.
    consumer_name:
        Default durable consumer name for pull subscriptions.
    """

    url: str = DEFAULT_NATS_URL
    subject_prefix: str = DEFAULT_SUBJECT_PREFIX
    stream_name: str = DEFAULT_STREAM_NAME
    max_msg_size: int = DEFAULT_MAX_MSG_SIZE
    reconnect_wait_ms: int = DEFAULT_RECONNECT_WAIT_MS
    max_reconnects: int = DEFAULT_MAX_RECONNECTS
    consumer_name: str = DEFAULT_CONSUMER_NAME

    def __post_init__(self) -> None:  # pragma: no cover - validation only
        if not (self.url.startswith("nats://") or self.url.startswith("tls://")):
            raise ValueError(
                f"Invalid NATS URL {self.url!r}. Expected 'nats://...' or 'tls://...'"
            )

    @property
    def events_subject(self) -> str:
        """Wildcard subject matching all NerveCenter events."""
        return f"{self.subject_prefix}.>"

    def subject_for_event(self, category: str, event_type: str) -> str:
        """Build the NATS subject for a specific event.

        The resulting subject follows the pattern
        ``{prefix}.{category}.{event_type}``.
        """
        return f"{self.subject_prefix}.{category}.{event_type}"


def _retention_limits() -> Any:
    """Return the JetStream *limits* retention policy across nats-py versions.

    The ``api.RetentionPolicy`` enum member names differ between releases
    (``LIMITS`` vs ``LIMITED``), so resolve it defensively.
    """
    try:
        enum = api.RetentionPolicy
        value = getattr(enum, "LIMITS", None)
        if value is None:
            value = getattr(enum, "LIMITED", None)
        if value is not None:
            return value
    except Exception:  # noqa: BLE001
        pass
    # The JetStream wire value for the limits retention policy.
    return 1


def config_from_env() -> NATSConfig:
    """Build a :class:`NATSConfig` from the process environment.

    Reads ``NERVECENTER_NATS_*`` variables; falls back to defaults.
    """

    url = os.environ.get(ENV_NATS_URL) or DEFAULT_NATS_URL

    def _int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None or not raw.strip():
            return default
        try:
            return int(raw)
        except ValueError:
            log.warning("nats.config.bad_int", name=name, raw=raw, using_default=default)
            return default

    return NATSConfig(
        url=url,
        subject_prefix=os.environ.get("NERVECENTER_NATS_SUBJECT_PREFIX", DEFAULT_SUBJECT_PREFIX),
        stream_name=os.environ.get("NERVECENTER_NATS_STREAM_NAME", DEFAULT_STREAM_NAME),
        max_msg_size=_int("NERVECENTER_NATS_MAX_MSG_SIZE", DEFAULT_MAX_MSG_SIZE),
        reconnect_wait_ms=_int("NERVECENTER_NATS_RECONNECT_WAIT_MS", DEFAULT_RECONNECT_WAIT_MS),
        max_reconnects=_int("NERVECENTER_NATS_MAX_RECONNECTS", DEFAULT_MAX_RECONNECTS),
        consumer_name=os.environ.get("NERVECENTER_NATS_CONSUMER_NAME", DEFAULT_CONSUMER_NAME),
    )


# ---------------------------------------------------------------------------
# Async NATS client wrapper
# ---------------------------------------------------------------------------


class NatsClient:
    """Async wrapper around the NATS connection and JetStream context.

    Manages the full lifecycle of the NATS connection:

    - :meth:`connect` — open the connection and obtain the JetStream context.
    - :meth:`ensure_stream` — idempotently create or update the JetStream stream.
    - :meth:`ensure_consumer` — idempotently create a durable consumer.
    - :attr:`jetstream` — access the :class:`JetStreamContext`.
    - :meth:`disconnect` — cleanly close the connection.
    - :attr:`is_connected` — check connection status.
    - :meth:`health_check` — verify connectivity and JetStream availability.

    Usage::

        config = config_from_env()
        client = NatsClient(config)
        await client.connect()
        try:
            js = client.jetstream
            await js.publish("nervcenter.system.started", b"{}")
        finally:
            await client.disconnect()
    """

    def __init__(self, config: NATSConfig | None = None) -> None:
        self._config = config or config_from_env()
        self._client: NatsConnection | None = None
        self._js: JetStreamContext | None = None
        self._connected = False

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the NATS server and initialize the JetStream context.

        Raises
        ------
        ConnectionError
            If the NATS server cannot be reached.
        """
        if self._connected:
            log.warning("nats.already_connected", url=self._config.url)
            return

        log.info("nats.connecting", url=self._config.url)

        client: NatsConnection
        try:
            client = await nats.connect(
                servers=[self._config.url],
                allow_reconnect=True,
                max_reconnect_attempts=self._config.max_reconnects,
                reconnect_time_wait=self._config.reconnect_wait_ms / 1000.0,
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnect,
                reconnected_cb=self._on_reconnect,
            )
        except Exception as exc:
            log.error("nats.connect_failed", url=self._config.url, error=str(exc))
            raise ConnectionError(
                f"Failed to connect to NATS server at {self._config.url}"
            ) from exc

        self._client = client
        # Obtain the JetStream context.
        self._js = client.jetstream()
        self._connected = True
        log.info("nats.connected", url=self._config.url)

        # The payload limit is advertised by the server in the INFO
        # frame (nats-py exposes it via ``client.max_payload``); check it
        # against our configured expectation without failing the connect.
        server_max = client.max_payload
        if server_max is not None and server_max < self._config.max_msg_size:
            log.warning(
                "nats.payload_limit_smaller",
                server_max=server_max,
                configured_max=self._config.max_msg_size,
            )

    async def disconnect(self) -> None:
        """Cleanly disconnect from the NATS server.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        if self._client is None:
            return
        try:
            await self._client.drain()
        except Exception:
            log.warning("nats.drain_failed", detail="Connection may already be closed")
        finally:
            self._client = None
            self._js = None
            self._connected = False
            log.info("nats.disconnected")

    # -- context manager -----------------------------------------------------

    async def __aenter__(self) -> NatsClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    # -- properties ----------------------------------------------------------

    @property
    def config(self) -> NATSConfig:
        """Return the configuration used by this client."""
        return self._config

    @property
    def jetstream(self) -> JetStreamContext:
        """Return the JetStream context.

        Raises
        ------
        RuntimeError
            If the client is not connected.
        """
        if self._js is None:
            raise RuntimeError("NatsClient is not connected. Call connect() first.")
        return self._js

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the client is currently connected."""
        return self._connected

    # -- stream / consumer management ----------------------------------------

    async def ensure_stream(
        self,
        *,
        name: str | None = None,
        subjects: list[str] | None = None,
        retention: Any = None,
        max_age: float = 72 * 3600,  # 72 hours
        max_msgs: int = -1,
        max_bytes: int = -1,
    ) -> Any:
        """Idempotently create or update the JetStream event stream.

        Parameters
        ----------
        name:
            Stream name; defaults to the configured ``stream_name``.
        subjects:
            Subjects to map to this stream; defaults to
            ``[config.events_subject]``.
        retention:
            JetStream retention policy (defaults to the limits policy when
            ``None``).
        max_age:
            Maximum age of messages in seconds.
        max_msgs:
            Maximum number of messages (``-1`` = unlimited).
        max_bytes:
            Maximum total bytes (``-1`` = unlimited).

        Returns
        -------
        nats.js.api.StreamInfo
            The stream info after creation or update.
        """
        js = self.jetstream
        stream_name = name or self._config.stream_name
        stream_subjects = subjects or [self._config.events_subject]

        # Check whether the stream already exists.
        try:
            info = await js.stream_info(stream_name)
            log.info("nats.stream_exists", stream=stream_name)
            return info
        except Exception:
            # NotFound (or equivalent) → create below.
            pass

        if retention is None:
            retention = _retention_limits()

        config = api.StreamConfig(
            name=stream_name,
            subjects=stream_subjects,
            retention=retention,
            max_age=max_age,
            max_msgs=max_msgs,
            max_bytes=max_bytes,
            storage=api.StorageType.FILE,
        )
        stream_info = await js.add_stream(config=config)
        log.info("nats.stream_created", stream=stream_name, subjects=stream_subjects)
        return stream_info

    async def ensure_consumer(
        self,
        *,
        consumer_name: str | None = None,
        stream_name: str | None = None,
        ack_wait: int = 30,
        max_ack: int = 3,
    ) -> Any:
        """Idempotently create a durable JetStream consumer.

        Parameters
        ----------
        consumer_name:
            Durable consumer name; defaults to the configured
            ``consumer_name``.
        stream_name:
            JetStream stream to attach to; defaults to the configured
            ``stream_name``.
        ack_wait:
            Acknowledgment wait in seconds.
        max_ack:
            Maximum redeliveries before a message is dead-lettered.

        Returns
        -------
        nats.js.api.ConsumerInfo
            The consumer info (freshly created or pre-existing).
        """
        js = self.jetstream
        stream = stream_name or self._config.stream_name
        name = consumer_name or self._config.consumer_name

        try:
            info = await js.consumer_info(stream, name)
            log.info("nats.consumer_exists", consumer=name, stream=stream)
            return info
        except Exception:
            # Consumer not found → create below.
            pass

        info = await js.add_consumer(
            stream,
            config=ConsumerConfig(
                durable=name,
                ack_wait=ack_wait,
                max_ack=max_ack,
            ),
        )
        log.info("nats.consumer_created", consumer=name, stream=stream)
        return info

    # -- health ----------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Return a structured health report for the NATS connection.

        Returns
        -------
        dict
            Contains ``connected``, ``jetstream_available``, ``server_info``,
            and ``error`` keys.
        """
        report: dict[str, Any] = {
            "connected": self._connected,
            "jetstream_available": self._js is not None,
            "server_info": None,
            "error": None,
        }
        if self._client is None or not self._connected:
            report["error"] = "Not connected"
            return report

        try:
            info = getattr(self._client, "_server_info", None) or {}
            if info:
                report["server_info"] = {
                    "server_id": info.get("server_id") or info.get("id"),
                    "version": info.get("version"),
                    "git_commit": info.get("git_commit"),
                }
        except Exception as exc:
            report["error"] = str(exc)
        return report

    # -- connection event handlers ---------------------------------------------

    @staticmethod
    async def _on_reconnect(client: NatsConnection) -> None:
        log.info("nats.reconnected")

    @staticmethod
    async def _on_disconnect(client: NatsConnection, err: Any = None) -> None:
        log.warning("nats.disconnected_unexpected", error=str(err) if err else None)

    @staticmethod
    async def _on_error(client: NatsConnection, err: Any) -> None:
        log.error("nats.protocol_error", error=str(err))


__all__ = [
    "NATSConfig",
    "NatsClient",
    "config_from_env",
    "ENV_NATS_URL",
    "DEFAULT_NATS_URL",
]
