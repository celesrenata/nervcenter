"""Connector base interface and shared primitives.

This module implements the runtime side of the :class:`schemas.connectors.Connector`
descriptor (NerveCenter spec Section 10 / Section 16, "Connectors"). It defines:

- :class:`Connector` — the abstract base class every external-system
  connector must implement. Provides a uniform lifecycle (``connect`` /
  ``disconnect`` / ``health_check``), a point-in-time :meth:`snapshot`,
  a live-event :meth:`subscribe` loop, and a helper to emit
  :class:`schemas.events.Event` records onto the NATS event bus via the
  :class:`~backend.events.publisher.EventPublisher`.

- :class:`Snapshot` — the payload returned by :meth:`Connector.snapshot`;
  a small, JSON-serializable container that carries the connector's
  point-in-time state plus a stable identity.

- :class:`ConnectorEvent` — a lightweight internal wrapper that
  describes a single live event a connector observed (before it is
  promoted to a bus :class:`~schemas.events.Event`).

- :class:`HTTPPool` — a small connection pool on top of
  ``httpx.AsyncClient`` with bounded concurrency and a simple
  exponential-backoff retry wrapper. Every HTTP-based connector should
  share one pool instance per connector so that TLS handshake cost is
  amortized and total open sockets stay bounded.

- :class:`RetryPolicy` — the retry knobs used by both :class:`HTTPPool`
  and the polling loops inside concrete connectors.

- :class:`ConnectorError` / :class:`ConnectError` / :class:`SnapshotError` —
  the exception hierarchy used across connectors. Callers should
  generally catch :class:`ConnectorError` and let subclasses signal
  specific failure modes.

Design notes
------------

* **Local-first**. Connectors never *require* a remote: a connector may
  talk to a local CLI (git, nix-store, nvidia-smi), a filesystem
  (``/proc``, ``/nix/store``), or a local HTTP service (Zoo, OmniRoute).
  Only :class:`~backend.connectors.kubernetes.KubernetesConnector`
  talks to an off-host control plane by default.

* **Event-driven**. The *primary* output of a connector is the
  :class:`schemas.events.Event` stream it publishes. The
  :meth:`Connector.snapshot` path is the *secondary* one: it exists so
  that a consumer can bootstrap from a point-in-time state before
  starting to receive live events.

* **Idempotent reconnect**. ``connect()`` must be safe to call twice;
  the connector either returns immediately if it is already connected,
  or resets its internal state and connects again.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Generic, TypeVar

import httpx
import structlog

from schemas.events import Event

log = structlog.get_logger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConnectorError(Exception):
    """Base class for all connector failures.

    Subclasses carry a :attr:`retryable` flag so that retry policies can
    distinguish transient failures (network blip, rate limit, 503) from
    permanent ones (auth failure, malformed config) without having to
    catch multiple exception types.
    """

    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ConnectError(ConnectorError):
    """Raised when :meth:`Connector.connect` cannot establish a session."""


class SnapshotError(ConnectorError):
    """Raised when :meth:`Connector.snapshot` cannot produce state."""


class SubscriptionError(ConnectorError):
    """Raised when :meth:`Connector.subscribe` fails to start its loop."""


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Exponential-backoff knobs shared across connectors.

    Parameters
    ----------
    max_attempts:
        Total attempts (initial + retries). ``1`` disables retrying.
    base_delay:
        Base delay in seconds. Delay for attempt ``n`` (0-indexed) is
        ``base_delay * (2 ** n)``.
    max_delay:
        Upper bound on a single delay.
    jitter:
        Random jitter in [0, 1) added to each delay to avoid thundering
        herds when many connectors retry simultaneously.
    retry_on:
        Predicate over the raised exception deciding whether to retry.
        Defaults to :func:`retryable`.
    """

    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 8.0
    jitter: float = 0.2

    def delay_for(self, attempt: int) -> float:
        """Return the delay in seconds to sleep before the given attempt.

        ``attempt`` is 0-indexed. The delay is capped at :attr:`max_delay`
        and augmented with up to :attr:`jitter` * delay as randomization.
        """
        raw = min(self.max_delay, self.base_delay * (2 ** attempt))
        if self.jitter <= 0.0:
            return raw
        import random

        return raw * (1.0 + random.random() * self.jitter)

    def should_retry(self, exc: BaseException) -> bool:
        """Return ``True`` when the failure warrants another attempt."""
        return bool(getattr(exc, "retryable", False))


# ---------------------------------------------------------------------------
# Snapshot + ConnectorEvent
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A point-in-time state snapshot produced by a connector.

    Snapshots are *not* persisted by the base class; a caller (or the
    persistence layer) decides what to do with them. The ``kind``
    identifier is stable per connector type so replay tooling can
    correlate a snapshot with the connector that produced it.

    Attributes
    ----------
    connector:
        The connector ``connector_type`` identifier (e.g. ``"git"``).
    captured_at:
        When the snapshot was taken (UTC).
    data:
        The arbitrary, JSON-serializable state captured by the connector.
        Each connector documents the keys it emits; consumers should
        treat unknown keys as opaque.
    healthy:
        Whether the connector was healthy at capture time. When
        ``False``, :attr:`error` carries the reason.
    error:
        Optional error message if the snapshot is degraded.
    """

    connector: str
    captured_at: datetime = field(default_factory=_utcnow)
    data: dict[str, Any] = field(default_factory=dict)
    healthy: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict of this snapshot."""
        return {
            "connector": self.connector,
            "captured_at": self.captured_at.isoformat(),
            "healthy": self.healthy,
            "error": self.error,
            "data": self.data,
        }


@dataclass(frozen=True, slots=True)
class ConnectorEvent:
    """A single observed event, prior to bus publication.

    Concrete connectors build :class:`ConnectorEvent` instances as they
    see external state change; the base class then maps each one into a
    canonical :class:`schemas.events.Event` and hands it to the
    :class:`~backend.events.publisher.EventPublisher`.

    Attributes
    ----------
    event_type:
        Machine-readable type, e.g. ``"git.commit"``.
    subject:
        Optional primary subject identifier (commit sha, pod name, ...).
    payload:
        Free-form event body; the connector is responsible for keeping
        it small enough to fit within the NATS max payload.
    occurred_at:
        When the phenomenon occurred (UTC); defaults to "now" at
        construction.
    severity:
        Operational severity. Defaults to ``info``; connectors should
        escalate to ``warning``/``error`` when state changes indicate
        trouble.
    idempotency_key:
        Optional dedup key. Connectors are expected to supply one when
        the underlying source has a stable identity (e.g. commit SHA,
        k8s event UID); the base class falls back to a UUID.
    """

    event_type: str
    subject: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=_utcnow)
    severity: str = "info"
    idempotency_key: str | None = None
    trace_id: str | None = None
    correlation_id: str | None = None


# ---------------------------------------------------------------------------
# HTTP connection pool
# ---------------------------------------------------------------------------


class HTTPPool:
    """Thin wrapper around :class:`httpx.AsyncClient` for connector use.

    The pool is designed for *shared* use across multiple HTTP calls
    from a single connector (and optionally across connectors of the
    same type). It enforces a bounded connection count so that a
    misbehaving upstream can't exhaust the process's file descriptors,
    and it exposes a :meth:`request` helper that applies the
    :class:`RetryPolicy`.

    The pool is a **context manager** and must be closed explicitly (or
    by the owning connector) when the connector disconnects.

    Usage::

        pool = HTTPPool(timeout=5.0, max_connections=10)
        await pool.aclose()  # or: async with pool:
        resp = await pool.request("GET", "https://example/x")
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 5.0,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
        verify: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._timeout = timeout
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive_connections
        self._headers = dict(headers or {})
        self._auth = auth
        self._verify = verify
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle ----------------------------------------------------------

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_keepalive,
            )
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                limits=limits,
                headers=self._headers,
                auth=self._auth,
                verify=self._verify,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the underlying client, if open. Idempotent."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> HTTPPool:
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    # -- request -------------------------------------------------------------

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: RetryPolicy | None = None,
    ) -> httpx.Response:
        """Issue an HTTP request with optional bounded retry.

        Parameters
        ----------
        method:
            HTTP method (``GET``, ``POST``, ...).
        url:
            Absolute or pool-relative URL.
        params, json, data, headers:
            Standard ``httpx`` arguments.
        timeout:
            Per-request timeout; overrides the pool default when set.
        retries:
            Optional :class:`RetryPolicy` to apply on transport /
            5xx / 429 responses. When ``None``, no retry happens.

        Returns
        -------
        httpx.Response
            The final response. Callers are expected to check
            ``response.status_code``; this method does *not* raise on
            4xx/5xx.
        """
        client = await self._ensure_client()
        policy = retries or RetryPolicy(max_attempts=1)

        last_exc: BaseException | None = None
        for attempt in range(max(1, policy.max_attempts)):
            try:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    data=data,
                    headers=headers,
                    timeout=timeout if timeout is not None else self._timeout,
                )
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt + 1 >= policy.max_attempts or not policy.should_retry(exc):
                    raise ConnectError(
                        f"HTTP request {method} {url} failed: {exc}",
                        retryable=True,
                    ) from exc
                await asyncio.sleep(policy.delay_for(attempt))
                continue

            # Retry on 429 and 5xx when retryable.
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt + 1 < policy.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else policy.delay_for(attempt)
                    except ValueError:
                        delay = policy.delay_for(attempt)
                    await asyncio.sleep(min(delay, policy.max_delay))
                    continue
            return response

        # Should be unreachable because the loop always either returns or raises.
        assert last_exc is not None
        raise ConnectError(f"HTTP retries exhausted for {method} {url}", retryable=True) from last_exc

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for :meth:`request` with method ``GET``."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Shortcut for :meth:`request` with method ``POST``."""
        return await self.request("POST", url, **kwargs)


# ---------------------------------------------------------------------------
# Async subprocess helper
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of running an external command via :func:`run_command`.

    Attributes
    ----------
    command:
        The argv list that was executed.
    returncode:
        Process exit code (``0`` on success).
    stdout:
        Captured standard output (text).
    stderr:
        Captured standard error (text).
    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def run_command(
    argv: list[str],
    *,
    cwd: str | None = None,
    timeout: float = 30.0,
    retries: RetryPolicy | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Run an external command asynchronously and capture its output.

    Connectors that shell out (git, nix-store, nvidia-smi, ...) should
    use this helper rather than ``asyncio.create_subprocess_exec``
    directly so they inherit the same error-handling semantics (bounded
    retry, timeout → ``SnapshotError`` with a clear message).

    Raises
    ------
    SnapshotError
        If the command times out, or all retry attempts fail with a
        spawn-level error (``FileNotFoundError`` etc.).
    """
    policy = retries or RetryPolicy(max_attempts=1)
    last_err: BaseException | None = None
    for attempt in range(max(1, policy.max_attempts)):
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()
                err = SnapshotError(
                    f"Command timed out after {timeout}s: {argv[0]!r}", retryable=True
                )
                if attempt + 1 < policy.max_attempts:
                    last_err = err
                    await asyncio.sleep(policy.delay_for(attempt))
                    continue
                raise err from None

            return CommandResult(
                command=tuple(argv),
                returncode=proc.returncode if proc.returncode is not None else -1,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
            )
        except FileNotFoundError as exc:
            err = SnapshotError(f"Executable not found: {argv[0]!r}")
            # Not retryable — the binary is not on PATH.
            last_err = err
            if not policy.should_retry(exc):
                raise err from exc
            await asyncio.sleep(policy.delay_for(attempt))
        except OSError as exc:
            err = SnapshotError(f"Failed to spawn {argv[0]!r}: {exc}", retryable=True)
            last_err = err
            if not policy.should_retry(exc):
                raise err from exc
            await asyncio.sleep(policy.delay_for(attempt))

    assert last_err is not None
    raise last_err


# ---------------------------------------------------------------------------
# Connector base class
# ---------------------------------------------------------------------------


class Connector(abc.ABC):
    """Abstract base class for every external-system connector.

    Subclasses **must** implement:

    - :meth:`_connect_internal` — establish any session / handle needed
      for later snapshots or live subscriptions.
    - :meth:`snapshot` — produce a :class:`Snapshot` from the external
      system.

    Subclasses **may** override:

    - :meth:`_subscribe_internal` — an async generator yielding
      :class:`ConnectorEvent` instances while the connector is live.
      The base class wraps it with retry, state tracking, and bus
      publication.
    - :meth:`describe` — build the :class:`schemas.connectors.Connector`
      descriptor. The base class supplies sensible defaults.

    Lifecycle
    ---------

    The base class manages the state transitions between
    ``disconnected`` → ``connecting`` → ``connected`` (and → ``degraded``
    / ``disabled`` on failure). Concrete connectors should not touch
    :attr:`status` directly; use the internal helpers
    (:meth:`_set_status`) which also log the transition.

    Events
    ------

    Every connector publishes lifecycle events onto the bus:

    - ``connector.connected`` on successful :meth:`connect`
    - ``connector.disconnected`` on :meth:`disconnect`
    - ``connector.error`` when an operation fails and is retryable

    Concrete connectors additionally publish their domain events (e.g.
    ``git.commit``, ``gpu.metrics``).
    """

    #: Connector type identifier, e.g. ``"git"``, ``"kubernetes"``.
    #: Subclasses must override this.
    connector_type: str = "generic"

    #: Capabilities this connector offers. Subclasses may extend.
    capabilities: list[str] = ["pull", "subscribe"]

    #: Transport used by this connector (see ``schemas.connectors``).
    transport: str = "local_api"

    #: Auth scheme (see ``schemas.connectors``).
    auth_scheme: str = "none"

    def __init__(
        self,
        *,
        name: str | None = None,
        endpoint: str | None = None,
        config: dict[str, Any] | None = None,
        credential_ref: str | None = None,
        publisher: Any | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.name = name or self.connector_type
        self.endpoint = endpoint
        self.config: dict[str, Any] = dict(config or {})
        self.credential_ref = credential_ref
        self._publisher = publisher
        self._retry = retry_policy or RetryPolicy()
        self._status: str = "disconnected"
        self._last_synced_at: datetime | None = None
        self._last_error: str | None = None
        self._connect_lock = asyncio.Lock()
        self._sub_task: asyncio.Task | None = None
        self._sub_running = False
        self._sub_last_emit: ConnectorEvent | None = None
        self._sub_emit_count = 0

    # -- properties ----------------------------------------------------------

    @property
    def status(self) -> str:
        """Current operational state (see ``ConnectorStatus`` literals)."""
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status == "connected"

    @property
    def last_synced_at(self) -> datetime | None:
        """Timestamp of the last successful snapshot / subscription tick."""
        return self._last_synced_at

    @property
    def last_error(self) -> str | None:
        """Most recent error, if any. Cleared on the next successful op."""
        return self._last_error

    @property
    def is_subscribing(self) -> bool:
        """Whether the live-subscription loop is currently running."""
        return self._sub_running

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the external system.

        Idempotent: if already connected, this is a no-op. On failure
        the connector transitions to ``degraded`` (or ``disabled`` if
        :attr:`config` marks it disabled) and raises :class:`ConnectError`.
        """
        async with self._connect_lock:
            if self._status == "connected":
                log.debug("connector.already_connected", connector=self.connector_type, name=self.name)
                return

            if self.config.get("disabled"):
                self._set_status("disabled", reason="disabled by config")
                raise ConnectError(f"Connector {self.name} is disabled by config")

            self._set_status("connecting")
            started = time.monotonic()
            try:
                await self._connect_internal()
            except ConnectorError:
                self._set_status("degraded")
                raise
            except Exception as exc:
                self._set_status("degraded", error=str(exc))
                raise ConnectError(
                    f"Connector {self.name} failed to connect: {exc}", retryable=True
                ) from exc

            self._set_status("connected")
            self._clear_error()
            log.info(
                "connector.connected",
                connector=self.connector_type,
                name=self.name,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )
            await self._emit_lifecycle("connector.connected", payload={"endpoint": self.endpoint})

    async def disconnect(self) -> None:
        """Disconnect from the external system. Idempotent."""
        async with self._connect_lock:
            if self._status in {"disconnected", "disabled"}:
                return
            try:
                await self._disconnect_internal()
            except Exception as exc:
                log.warning(
                    "connector.disconnect_error",
                    connector=self.connector_type,
                    name=self.name,
                    error=str(exc),
                )
            self._set_status("disconnected")
            log.info("connector.disconnected", connector=self.connector_type, name=self.name)
            await self._emit_lifecycle("connector.disconnected", payload={})

    async def __aenter__(self) -> Connector:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    # -- snapshot ------------------------------------------------------------

    async def snapshot(self) -> Snapshot:
        """Capture the connector's point-in-time state.

        The base class wraps :meth:`_snapshot_internal` with error
        handling: any exception is converted into a
        ``healthy=False`` :class:`Snapshot` (so callers can still
        observe *what went wrong*) and a ``connector.error`` bus event
        is emitted when the failure is retryable.
        """
        started = time.monotonic()
        try:
            data = await self._snapshot_internal()
        except SnapshotError as exc:
            log.error(
                "connector.snapshot_failed",
                connector=self.connector_type,
                name=self.name,
                error=str(exc),
            )
            self._last_error = str(exc)
            await self._emit_lifecycle(
                "connector.error",
                payload={"reason": str(exc), "kind": "snapshot"},
                severity="error" if not exc.retryable else "warning",
            )
            return Snapshot(
                connector=self.connector_type,
                data={},
                healthy=False,
                error=str(exc),
            )
        except Exception as exc:
            err = SnapshotError(f"Snapshot failed: {exc}", retryable=True)
            log.exception(
                "connector.snapshot_unexpected",
                connector=self.connector_type,
                name=self.name,
                error=str(exc),
            )
            self._last_error = str(err)
            await self._emit_lifecycle(
                "connector.error",
                payload={"reason": str(err), "kind": "snapshot"},
                severity="warning",
            )
            return Snapshot(
                connector=self.connector_type,
                data={},
                healthy=False,
                error=str(err),
            )

        self._last_synced_at = _utcnow()
        self._clear_error()
        log.debug(
            "connector.snapshot_ok",
            connector=self.connector_type,
            name=self.name,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            keys=sorted(data.keys()) if isinstance(data, dict) else None,
        )
        return Snapshot(connector=self.connector_type, data=data, healthy=True)

    # -- subscription --------------------------------------------------------

    async def subscribe(
        self,
        *,
        interval: float = 5.0,
        on_event: Any | None = None,
    ) -> None:
        """Start the live-event subscription loop.

        Parameters
        ----------
        interval:
            Polling interval in seconds (only meaningful for
            poll-based connectors). Stream-based connectors may ignore
            it and rely on the underlying transport's push cadence.
        on_event:
            Optional local callback invoked for every event before it is
            published to the bus. Useful for tests and for connectors
            that want to fan out to multiple sinks. Signature:
            ``async (event: ConnectorEvent) -> None``.

        Idempotent: calling :meth:`subscribe` while already subscribing
        is a no-op. Raises :class:`SubscriptionError` if the connector
        is not connected.
        """
        if self._status != "connected":
            raise SubscriptionError(
                f"Connector {self.name} is not connected (status={self._status}); call connect() first."
            )
        if self._sub_running:
            log.debug("connector.subscribe_noop", connector=self.connector_type)
            return

        self._sub_running = True
        self._sub_task = asyncio.create_task(
            self._sub_loop(interval=interval, on_event=on_event),
            name=f"connector-sub-{self.connector_type}-{self.name}",
        )
        log.info(
            "connector.subscribed",
            connector=self.connector_type,
            name=self.name,
            interval=interval,
        )

    async def unsubscribe(self) -> None:
        """Stop the live-event subscription loop (if running)."""
        self._sub_running = False
        if self._sub_task is not None:
            self._sub_task.cancel()
            try:
                await asyncio.wait_for(self._sub_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self._sub_task = None
        log.info("connector.unsubscribed", connector=self.connector_type, name=self.name)

    async def _sub_loop(self, *, interval: float, on_event: Any) -> None:
        """Run the subscription generator, publishing events to the bus.

        Each yielded :class:`ConnectorEvent` is:

        1. Invoked locally via ``on_event`` (if provided).
        2. Converted to a :class:`schemas.events.Event` and published
           onto the NATS bus (if a publisher is configured).
        3. Counted for diagnostics (``self._sub_emit_count``).

        The loop tolerates individual-event failures: an event that
        fails to publish is logged and dropped, but does not stop the
        loop. A fatal failure from the generator itself *does* stop the
        loop (and transitions the connector to ``degraded``).
        """
        try:
            async for event in self._subscribe_internal(interval=interval):
                await self._handle_connector_event(event, on_event=on_event)
        except ConnectorError as exc:
            if exc.retryable and self._status == "connected":
                self._set_status("degraded", error=str(exc))
            log.error(
                "connector.subscription_failed",
                connector=self.connector_type,
                name=self.name,
                error=str(exc),
            )
            await self._emit_lifecycle(
                "connector.error",
                payload={"reason": str(exc), "kind": "subscription"},
                severity="error",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "connector.subscription_unexpected",
                connector=self.connector_type,
                name=self.name,
                error=str(exc),
            )
            self._set_status("degraded", error=str(exc))
        finally:
            self._sub_running = False
            log.debug(
                "connector.subscription_ended",
                connector=self.connector_type,
                emitted=self._sub_emit_count,
            )

    async def _handle_connector_event(self, event: ConnectorEvent, *, on_event: Any) -> None:
        """Route a single :class:`ConnectorEvent` to the bus + local sink."""
        if on_event is not None:
            with contextlib.suppress(Exception):
                await on_event(event)

        self._sub_emit_count += 1
        self._sub_last_emit = event
        self._last_synced_at = _utcnow()

        if self._publisher is None:
            return

        try:
            bus_event = self._to_bus_event(event)
            await self._publisher.publish(bus_event)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "connector.event_publish_failed",
                connector=self.connector_type,
                event_type=event.event_type,
                error=str(exc),
            )

    # -- health --------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Return a structured health report for this connector.

        The report includes status, last-sync timestamp, subscription
        state, and — when the connector is healthy — a fresh
        :meth:`snapshot` summary.
        """
        report: dict[str, Any] = {
            "connector": self.connector_type,
            "name": self.name,
            "status": self._status,
            "endpoint": self.endpoint,
            "last_synced_at": self._last_synced_at.isoformat() if self._last_synced_at else None,
            "last_error": self._last_error,
            "subscribing": self._sub_running,
            "sub_emit_count": self._sub_emit_count,
            "capabilities": list(self.capabilities),
        }
        if self._status == "connected":
            snap = await self.snapshot()
            report["snapshot_healthy"] = snap.healthy
            report["snapshot_error"] = snap.error
        return report

    # -- descriptor ------------------------------------------------------------

    def describe(self) -> Any:
        """Build the :class:`schemas.connectors.Connector` descriptor.

        Subclasses may override to enrich the descriptor (e.g. with a
        custom ``emitted_event_types`` list).
        """
        from schemas.connectors import Connector as ConnectorRecord

        return ConnectorRecord(
            id=f"{self.connector_type}:{self.name}",
            connector_type=self.connector_type,
            name=self.name,
            status=self._status,  # type: ignore[arg-type]
            capabilities=list(self.capabilities),  # type: ignore[arg-type]
            transport=self.transport,  # type: ignore[arg-type]
            auth_scheme=self.auth_scheme,  # type: ignore[arg-type]
            endpoint=self.endpoint,
            config=dict(self.config),
            credential_ref=self.credential_ref,
            last_synced_at=self._last_synced_at,
            error=self._last_error,
            emitted_event_types=list(self.emitted_event_types()),
        )

    def emitted_event_types(self) -> list[str]:
        """Return the list of event types this connector can emit.

        The base class returns an empty list; subclasses should
        override.
        """
        return []

    # -- internal hooks (subclasses override) --------------------------------

    async def _connect_internal(self) -> None:
        """Establish any session needed for later snapshots / events.

        The base implementation is a no-op; file/CLI-based connectors
        typically do nothing here because each operation shells out
        independently.
        """

    async def _disconnect_internal(self) -> None:
        """Tear down the session; the base implementation is a no-op."""

    @abc.abstractmethod
    async def _snapshot_internal(self) -> dict[str, Any]:
        """Fetch the connector's current state.

        Must return a JSON-serializable dict. Raise
        :class:`SnapshotError` (with ``retryable=True`` for transient
        failures) when the source cannot be reached.
        """
        ...

    async def _subscribe_internal(self, *, interval: float) -> AsyncIterator[ConnectorEvent]:
        """Default implementation: poll :meth:`_snapshot_internal` and
        emit a synthetic ``{connector_type}.snapshot`` event on each
        call.

        Poll-based connectors should override this to yield
        *differential* events (only what changed) instead of repeating
        the full state on every tick.
        """
        while self._sub_running:
            await asyncio.sleep(max(0.0, interval))
            try:
                data = await self._snapshot_internal()
            except SnapshotError:
                # The base-class snapshot path handles retryable errors
                # by emitting connector.error; here we just skip the tick.
                continue
            yield ConnectorEvent(
                event_type=f"{self.connector_type}.snapshot",
                subject=self.name,
                payload=data,
                idempotency_key=f"{self.connector_type}:{self.name}:{int(time.time() * 1000)}",
            )

    # -- helpers ------------------------------------------------------------

    def _set_status(self, status: str, *, error: str | None = None, reason: str | None = None) -> None:
        prev = self._status
        self._status = status
        if error is not None:
            self._last_error = error
        elif status == "connected":
            self._clear_error()
        if prev != status:
            log.debug(
                "connector.status_changed",
                connector=self.connector_type,
                name=self.name,
                from_status=prev,
                to_status=status,
                reason=reason,
                error=error,
            )

    def _clear_error(self) -> None:
        self._last_error = None

    def _to_bus_event(self, event: ConnectorEvent) -> Event:
        """Convert a :class:`ConnectorEvent` into a canonical bus event."""
        return Event(
            id=str(uuid.uuid4()),
            event_type=event.event_type,
            category="connector",
            source=f"{self.connector_type}:{self.name}",
            subject=event.subject,
            payload=dict(event.payload),
            severity=event.severity,  # type: ignore[arg-type]
            occurred_at=event.occurred_at,
            trace_id=event.trace_id,
            correlation_id=event.correlation_id,
            idempotency_key=event.idempotency_key,
        )

    async def _emit_lifecycle(
        self,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        severity: str = "info",
    ) -> None:
        """Emit a connector-lifecycle event onto the bus, if configured."""
        if self._publisher is None:
            return
        try:
            bus_event = self._to_bus_event(
                ConnectorEvent(
                    event_type=event_type,
                    subject=self.name,
                    payload=payload or {},
                    severity=severity,
                    idempotency_key=f"{event_type}:{self.name}:{int(time.time() * 1000)}",
                )
            )
            await self._publisher.publish(bus_event)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "connector.lifecycle_emit_failed",
                connector=self.connector_type,
                event_type=event_type,
                error=str(exc),
            )


__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectError",
    "SnapshotError",
    "SubscriptionError",
    "RetryPolicy",
    "Snapshot",
    "ConnectorEvent",
    "HTTPPool",
    "CommandResult",
    "run_command",
]
