"""Host connector: system resource snapshots.

Implements the NerveCenter connector for host system resources (spec
Section 44, "Connectors"). It captures CPU, memory, disk, and network
metrics via ``psutil``.

Capabilities
------------

* **Point-in-time snapshot** (:meth:`snapshot` / :meth:`_snapshot_internal`)
  — captures:

  - ``cpu`` — percent usage, frequency, and usage delta since last poll
  - ``memory`` — total/available/used/percent plus swap metrics
  - ``disk`` — per-partition usage (total/used/free/percent)
  - ``network`` — per-interface delta since last poll

* **Live event subscription** (:meth:`subscribe` / :meth:`_subscribe_internal`)
  — emits ``host.metrics`` events at the configured interval.

Usage::

    from backend.connectors import HostConnector

    connector = HostConnector(name="my-host")

    await connector.connect()
    snap = await connector.snapshot()
    print(snap.data["memory"]["percent"])

    collected: list = []
    async def on_event(e): collected.append(e)

    await connector.subscribe(interval=5.0, on_event=on_event)
    ...

    await connector.unsubscribe()
    await connector.disconnect()
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import psutil
import structlog

from .base import (
    ConnectError,
    Connector,
    ConnectorEvent,
)

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class HostConnector(Connector):
    """Connector to host system resources.

    Captures CPU, memory, disk, and network usage.

    Parameters
    ----------
    name:
        Human-readable name for this connector instance.
    """

    connector_type = "host"
    capabilities = ["pull", "subscribe"]
    transport = "local_api"
    auth_scheme = "none"

    def __init__(self, *, name: str | None = None, **kwargs: Any) -> None:
        super().__init__(name=name or "host", **kwargs)
        self._last_cpu_times: tuple[float, ...] | None = None
        self._last_net_io: dict[str, Any] | None = None

    async def _connect_internal(self) -> None:
        """Verify psutil is available."""
        try:
            psutil.cpu_percent()
        except Exception as exc:
            raise ConnectError(f"psutil unavailable: {exc}") from exc

    async def _disconnect_internal(self) -> None:
        """No-op for host connector."""
        pass

    async def _snapshot_internal(self) -> dict[str, Any]:
        """Capture current system resource state."""
        cpu = self._cpu_usage()
        mem = self._memory_usage()
        disk = self._disk_usage()
        net = self._network_usage()
        return {
            "cpu": cpu,
            "memory": mem,
            "disk": disk,
            "network": net,
            "snapshot_at": _utcnow().isoformat(),
        }

    async def _subscribe_internal(self, *, interval: float) -> AsyncIterator[ConnectorEvent]:
        """Poll for system resource changes."""
        while self._sub_running:
            await asyncio.sleep(max(0.05, interval))
            try:
                snapshot = await self._snapshot_internal()
                yield ConnectorEvent(
                    event_type="host.metrics",
                    subject="system",
                    payload=snapshot,
                    occurred_at=_utcnow(),
                )
            except Exception as exc:
                log.error(
                    "host.poll_failed",
                    error=str(exc),
                )
                continue

    def _cpu_usage(self) -> dict[str, Any]:
        """Return current CPU usage metrics."""
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_times = psutil.cpu_times()

        # Calculate CPU usage since last call
        cpu_usage = 0.0
        if self._last_cpu_times is not None:
            total_time = sum(
                getattr(cpu_times, field) - self._last_cpu_times[i]
                for i, field in enumerate(["user", "nice", "system", "idle"])
            )
            idle_time = cpu_times.idle - self._last_cpu_times[3]
            if total_time > 0:
                cpu_usage = (1.0 - idle_time / total_time) * 100.0

        self._last_cpu_times = (
            cpu_times.user,
            cpu_times.nice,
            cpu_times.system,
            cpu_times.idle,
        )

        return {
            "percent": cpu_percent,
            "usage": cpu_usage,
            "count": psutil.cpu_count(),
            "frequency": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        }

    def _memory_usage(self) -> dict[str, Any]:
        """Return current memory usage metrics."""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }

    def _disk_usage(self) -> dict[str, Any]:
        """Return current disk usage metrics."""
        partitions = psutil.disk_partitions()
        disks = {}
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks[partition.device] = {
                    "mountpoint": partition.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            except Exception as exc:
                log.warning(
                    "host.disk_usage_failed",
                    device=partition.device,
                    error=str(exc),
                )
        return disks

    def _network_usage(self) -> dict[str, Any]:
        """Return current network usage metrics."""
        net_io = psutil.net_io_counters(pernic=True)
        net_stats = {}

        if self._last_net_io is not None:
            for nic, stats in net_io.items():
                if nic in self._last_net_io:
                    last_stats = self._last_net_io[nic]
                    net_stats[nic] = {
                        "bytes_sent": stats.bytes_sent - last_stats.bytes_sent,
                        "bytes_recv": stats.bytes_recv - last_stats.bytes_recv,
                        "packets_sent": stats.packets_sent - last_stats.packets_sent,
                        "packets_recv": stats.packets_recv - last_stats.packets_recv,
                    }

        self._last_net_io = net_io
        return net_stats

    def emitted_event_types(self) -> list[str]:
        return [
            "host.metrics",
        ]


__all__ = ["HostConnector"]
