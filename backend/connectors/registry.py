"""Connector registry: discovery and factory for external-system integrations.

This module provides the registry that owns all known connector types and
instantiates them from configuration. It is designed to support:

- **Automatic registration** of connector subclasses via the
  :class:`ConnectorRegistry.register` decorator (or explicit
  :meth:`register_connector`).

- **Dynamic instantiation** from YAML/JSON configs via :meth:`create`
  which inspects the ``type`` field and dispatches to the appropriate
  :class:`Connector` subclass.

- **Health monitoring** via :meth:`health_all` which returns a
  consolidated report for all registered connectors.

Usage::

    registry = ConnectorRegistry()
    registry.register(GitConnector)
    registry.register(KubernetesConnector)

    config = {"type": "git", "name": "main", "repo": "/src/nervcenter"}
    connector = registry.create(config)

    await registry.connect_all()
    try:
        for snap in await registry.snapshot_all():
            print(snap.connector, snap.data.keys())
    finally:
        await registry.disconnect_all()

Design notes
------------

* **No runtime introspection**. The registry does not dynamically scan
  modules for subclasses (to avoid import-time side effects and to keep
  the set of available connectors explicit). Instead, callers register
  the types they care about.

* **Stateful**. The registry keeps track of which connectors are
  currently connected (so :meth:`disconnect_all` only affects
  connected instances).

* **Publisher propagation**. If the registry is given an
  :class:`~backend.events.publisher.EventPublisher`, every connector
  created from it receives the same publisher so that all events
  converge onto the same NATS stream.

* **Dependency injection**. Most connectors accept optional
  :class:`~backend.connectors.base.HTTPPool` and
  :class:`~backend.connectors.base.RetryPolicy` arguments, which the
  registry will pass through when supplied.
"""

from __future__ import annotations

from typing import Any, TypeVar

from schemas.connectors import Connector as ConnectorRecord

from .base import (
    ConnectError,
    Connector,
    HTTPPool,
    RetryPolicy,
    Snapshot,
)

__all__ = [
    "ConnectorRegistry",
    "ConnectorNotFoundError",
    "AlreadyRegisteredError",
    "NotConnectedError",
]

T = TypeVar("T", bound=Connector)


class AlreadyRegisteredError(Exception):
    """Raised when attempting to register a connector type that is already
    registered."""

    def __init__(self, connector_type: str) -> None:
        super().__init__(f"Connector type {connector_type!r} is already registered")
        self.connector_type = connector_type


class ConnectorNotFoundError(Exception):
    """Raised when :meth:`create` is given a type that is not registered."""

    def __init__(self, connector_type: str) -> None:
        super().__init__(f"Unknown connector type {connector_type!r}")
        self.connector_type = connector_type


class NotConnectedError(Exception):
    """Raised when an operation requires a connector to be connected but it is not."""

    def __init__(self, connector_name: str) -> None:
        super().__init__(f"Connector {connector_name!r} is not connected")
        self.connector_name = connector_name


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ConnectorRegistry:
    """Factory and lifecycle manager for :class:`~.base.Connector` instances.

    Parameters
    ----------
    publisher:
        Optional event publisher to inject into every connector created
        by this registry.
    pool:
        Optional shared :class:`~.base.HTTPPool` instance. When set, it
        is passed to every connector that accepts one.
    retry_policy:
        Optional :class:`~.base.RetryPolicy`. When set, it is passed to
        every connector.
    """

    def __init__(
        self,
        *,
        publisher: Any = None,
        pool: HTTPPool | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._classes: dict[str, type[Connector]] = {}
        self._instances: dict[str, Connector] = {}
        self._publisher = publisher
        self._pool = pool
        self._retry = retry_policy or RetryPolicy()

    # -- registration --------------------------------------------------------

    def register(self, cls: type[T]) -> type[T]:
        """Decorator to register a :class:`~.base.Connector` subclass.

        Parameters
        ----------
        cls:
            A subclass of :class:`~.base.Connector` with a non-empty
            ``connector_type`` class attribute.

        Returns
        -------
        type[T]
            The same class (so it can be used as ``@registry.register``
            on a class definition).

        Raises
        ------
        AlreadyRegisteredError
            When ``cls.connector_type`` is already registered.
        """
        if not hasattr(cls, "connector_type") or not cls.connector_type:
            raise ValueError(f"{cls.__name__} must define a non-empty connector_type")

        connector_type = cls.connector_type
        if connector_type in self._classes:
            raise AlreadyRegisteredError(connector_type)

        self._classes[connector_type] = cls
        return cls

    def register_connector(self, connector_type: str, cls: type[T]) -> None:
        """Explicit registration helper (alternative to decorator)."""
        if connector_type in self._classes:
            raise AlreadyRegisteredError(connector_type)
        self._classes[connector_type] = cls

    def unregister(self, connector_type: str) -> None:
        """Remove a connector type from the registry. Does not disconnect
        existing instances."""
        self._classes.pop(connector_type, None)

    # -- creation -------------------------------------------------------------

    def create(
        self,
        config: dict[str, Any],
        *,
        name: str | None = None,
        endpoint: str | None = None,
        pool: HTTPPool | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> Connector:
        """Instantiate a connector from a configuration dict.

        The ``config`` dict must contain a ``type`` key whose value
        matches a registered connector type. Additional keys are passed
        as keyword arguments to the connector's ``__init__``.

        Parameters
        ----------
        config:
            Configuration dict. Required keys: ``type``. Optional keys:
            ``name``, ``endpoint``, ``config``, ``credential_ref``,
            and any connector-specific parameters.
        name:
            Optional override for ``config["name"]``.
        endpoint:
            Optional override for ``config["endpoint"]``.
        pool:
            Optional pool override (uses registry pool when omitted).
        retry_policy:
            Optional retry override (uses registry policy when omitted).

        Returns
        -------
        Connector
            An instance of the registered connector class.

        Raises
        ------
        ConnectorNotFoundError
            When ``config["type"]`` is not registered.
        """
        connector_type = config.get("type")
        if not connector_type:
            raise ValueError("Config must contain 'type' key")
        if connector_type not in self._classes:
            raise ConnectorNotFoundError(connector_type)

        cls = self._classes[connector_type]
        kwargs: dict[str, Any] = {
            "name": name or config.get("name", connector_type),
            "endpoint": endpoint or config.get("endpoint"),
            "config": dict(config.get("config", {})),
            "credential_ref": config.get("credential_ref"),
            "publisher": self._publisher,
            "retry_policy": retry_policy or self._retry,
        }

        # connector-specific args
        for key, value in config.items():
            if key not in {"type", "name", "endpoint", "config", "credential_ref"}:
                kwargs[key] = value

        connector = cls(**kwargs)

        # Inject shared pool if available and accepted by the connector.
        if pool is not None:
            self._inject_pool(connector, pool)
        elif self._pool is not None:
            self._inject_pool(connector, self._pool)

        self._instances[connector.name] = connector
        return connector

    def _inject_pool(self, connector: Connector, pool: HTTPPool) -> None:
        """Attempt to inject the shared pool into a connector.

        Connectors that use HTTP (e.g. Kubernetes, OmniRoute, Zoo) have
        a ``pool`` attribute or accept a ``pool=`` kwarg. This helper
        tries a few conventional ways to wire the pool.
        """
        if hasattr(connector, "pool"):
            connector.pool = pool

    def create_many(self, configs: list[dict[str, Any]]) -> list[Connector]:
        """Instantiate multiple connectors from a list of configs."""
        return [self.create(cfg) for cfg in configs]

    # -- lifecycle -----------------------------------------------------------

    async def connect(self, name: str) -> None:
        """Connect a single connector by name.

        Raises
        ------
        KeyError
            When no connector with that name exists.
        ConnectError
            When the connector's connect phase fails.
        """
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        await self._instances[name].connect()

    async def disconnect(self, name: str) -> None:
        """Disconnect a single connector by name."""
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        await self._instances[name].disconnect()

    async def connect_all(self) -> list[tuple[str, str | None]]:
        """Connect all registered connectors.

        Returns
        -------
        list[tuple[str, str | None]]
            One entry per connector: ``(name, error_or_none)``. If
            connection fails, the error string is the second element.
        """
        results: list[tuple[str, str | None]] = []
        for name, connector in self._instances.items():
            try:
                await connector.connect()
                results.append((name, None))
            except ConnectError as exc:
                results.append((name, str(exc)))
        return results

    async def disconnect_all(self) -> list[str]:
        """Disconnect all connectors that are currently connected.

        Returns
        -------
        list[str]
            Names of connectors that were disconnected.
        """
        disconnected: list[str] = []
        for name, connector in self._instances.items():
            try:
                await connector.disconnect()
                disconnected.append(name)
            except Exception:
                # Best-effort disconnect; log and continue
                pass
        return disconnected

    # -- snapshot ------------------------------------------------------------

    async def snapshot(self, name: str) -> Snapshot:
        """Request a point-in-time snapshot from a single connector.

        Raises
        ------
        KeyError
            When the connector is not registered.
        """
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        return await self._instances[name].snapshot()

    async def snapshot_all(self) -> list[Snapshot]:
        """Request snapshots from all connectors.

        Returns
        -------
        list[Snapshot]
            Snapshots in the order of :attr:`_instances`. Unhealthy
            snapshots carry ``healthy=False`` and a descriptive error.
        """
        snapshots: list[Snapshot] = []
        for connector in self._instances.values():
            snapshots.append(await connector.snapshot())
        return snapshots

    # -- subscription --------------------------------------------------------

    async def subscribe(
        self,
        name: str,
        *,
        interval: float = 5.0,
        on_event: Any = None,
    ) -> None:
        """Start the live-event subscription for a single connector.

        Raises
        ------
        KeyError
            When the connector is not registered.
        NotConnectedError
            When the connector is not connected.
        """
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        connector = self._instances[name]
        if not connector.is_connected:
            raise NotConnectedError(name)
        await connector.subscribe(interval=interval, on_event=on_event)

    async def unsubscribe(self, name: str) -> None:
        """Stop the live-event subscription for a single connector."""
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        await self._instances[name].unsubscribe()

    async def subscribe_all(
        self,
        *,
        interval: float = 5.0,
        on_event: Any = None,
    ) -> dict[str, str | None]:
        """Start subscriptions for all connectors.

        Parameters
        ----------
        interval:
            Polling interval (see :meth:`Connector.subscribe`).
        on_event:
            Optional callback for all events.

        Returns
        -------
        dict[str, str | None]
            Map of connector name to error string (``None`` on success).
        """
        results: dict[str, str | None] = {}
        for name, connector in self._instances.items():
            try:
                if not connector.is_connected:
                    results[name] = "not_connected"
                    continue
                await connector.subscribe(interval=interval, on_event=on_event)
                results[name] = None
            except Exception as exc:
                results[name] = str(exc)
        return results

    async def unsubscribe_all(self) -> dict[str, str | None]:
        """Stop subscriptions for all connectors.

        Returns
        -------
        dict[str, str | None]
            Map of connector name to error string (``None`` on success).
        """
        results: dict[str, str | None] = {}
        for name, connector in self._instances.items():
            try:
                await connector.unsubscribe()
                results[name] = None
            except Exception as exc:
                results[name] = str(exc)
        return results

    # -- health --------------------------------------------------------------

    async def health(self, name: str) -> dict[str, Any]:
        """Return health report for a single connector."""
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        return await self._instances[name].health_check()

    async def health_all(self) -> dict[str, dict[str, Any]]:
        """Return health reports for all connectors."""
        reports: dict[str, dict[str, Any]] = {}
        for name, connector in self._instances.items():
            reports[name] = await connector.health_check()
        return reports

    def describe(self, name: str) -> ConnectorRecord:
        """Return the :class:`~schemas.connectors.Connector` descriptor for
        a single connector."""
        if name not in self._instances:
            raise KeyError(f"Unknown connector instance {name!r}")
        return self._instances[name].describe()

    def describe_all(self) -> list[ConnectorRecord]:
        """Return descriptors for all connectors."""
        return [conn.describe() for conn in self._instances.values()]

    def connector_names(self) -> list[str]:
        """List names of all registered connector instances."""
        return list(self._instances.keys())

    def registered_types(self) -> list[str]:
        """List connector types that are registered (not necessarily
        instantiated)."""
        return list(self._classes.keys())


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def make_default_registry(
    *,
    publisher: Any = None,
) -> ConnectorRegistry:
    """Return a registry with all built-in connector types registered.

    This is a convenience function that callers can use when they want
    the standard set of connectors (Git, Kubernetes, Host, GPU, Nix,
    OmniRoute, Zoo) without manually registering each one.

    Parameters
    ----------
    publisher:
        Optional event publisher to inject into every connector.

    Returns
    -------
    ConnectorRegistry
        A pre-configured registry with types registered.
    """
    from .git import GitConnector
    from .gpu import GPUConnector
    from .host import HostConnector
    from .kubernetes import KubernetesConnector
    from .nix import NixConnector
    from .omniroute import OmniRouteConnector
    from .zoo import ZooConnector

    registry = ConnectorRegistry(publisher=publisher)
    registry.register(GitConnector)
    registry.register(KubernetesConnector)
    registry.register(HostConnector)
    registry.register(GPUConnector)
    registry.register(NixConnector)
    registry.register(OmniRouteConnector)
    registry.register(ZooConnector)
    return registry


__all__ = [
    "ConnectorRegistry",
    "ConnectorNotFoundError",
    "AlreadyRegisteredError",
    "NotConnectedError",
    "make_default_registry",
]
