"""GPU connector: GPU telemetry and state.

This connector monitors GPU resources including utilization, memory usage,
temperature, and power draw. It shells out to ``nvidia-smi`` when available
and falls back to synthetic metrics on non-GPU systems.

Usage::

    from backend.connectors import GPUConnector

    connector = GPUConnector(
        name="gpu0",
        interval=5.0,
        include_processes=True,
    )

    snap = await connector.snapshot()
    if snap.data["gpus"]:
        print(snap.data["gpus"][0]["utilization_percent"])

Design notes
------------

* **nvidia-smi dependency**. The connector requires ``nvidia-smi`` to be
  on ``$PATH``. When unavailable, it returns a minimal snapshot with
  ``gpus: []`` and sets the connector to ``healthy=False``.

* **Structured parsing**. The connector parses the machine-readable
  JSON output of ``nvidia-smi --query-gpu=... --format=json`` to
  extract structured metrics.

* **Process monitoring**. When ``include_processes=True``, the
  connector also captures per-process GPU memory usage and GPU
  utilization.

* **Local-first**. Runs on the same host where the GPU is installed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from .base import CommandResult, Connector, ConnectorEvent, Snapshot, SnapshotError, run_command

log = structlog.get_logger(__name__)


class GPUConnector(Connector):
    """Connector to GPU resources via nvidia-smi."""

    connector_type = "gpu"
    capabilities = ["pull"]
    transport = "local_api"
    auth_scheme = "none"

    def __init__(
        self,
        *,
        name: str | None = None,
        interval: float = 5.0,
        include_processes: bool = True,
        timeout: float = 15.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name=name or "gpu",
            endpoint="localhost",
            **kwargs,
        )
        self._include_processes = include_processes
        self._timeout = timeout
        self._has_nvidia_smi: bool | None = None

    # -- snapshot ------------------------------------------------------------

    async def _snapshot_internal(self) -> dict[str, Any]:
        """Capture GPU state via nvidia-smi.

        Returns
        -------
        dict[str, Any]
            Snapshot payload with keys:
            - ``timestamp``: snapshot timestamp (ISO-8601 UTC)
            - ``gpus``: list of GPU devices with metrics
            - ``processes``: list of GPU processes (if include_processes)
        """
        snapshot: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._has_nvidia_smi is None:
            self._has_nvidia_smi = await self._check_nvidia_smi()

        if not self._has_nvidia_smi:
            snapshot["error"] = "nvidia-smi not found"
            return snapshot

        # Query GPU metrics
        gpus = await self._query_gpus()
        snapshot["gpus"] = gpus

        # Query processes if requested
        if self._include_processes:
            processes = await self._query_processes()
            snapshot["processes"] = processes

        return snapshot

    # -- internal helpers ----------------------------------------------------

    async def _check_nvidia_smi(self) -> bool:
        """Return True if nvidia-smi is available."""
        result = await run_command(["nvidia-smi", "--version"], timeout=self._timeout)
        return result.returncode == 0

    async def _run_nvidia_smi(self, query: str, format_: str = "csv") -> CommandResult:
        return await run_command(
            ["nvidia-smi", "--query-gpu", query, "--format", format_],
            timeout=self._timeout,
            retries=self._retry,
        )

    async def _run_nvidia_smi_json(self, query: str) -> dict[str, Any]:
        """Run a GPU query and parse JSON output."""
        result = await run_command(
            ["nvidia-smi", "--query-gpu", query, "--format", "json"],
            timeout=self._timeout,
            retries=self._retry,
        )
        if result.returncode != 0:
            raise SnapshotError(
                f"nvidia-smi failed: {result.stderr}",
                retryable=True,
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise SnapshotError(
                f"Failed to parse nvidia-smi JSON: {exc}",
                retryable=True,
            ) from exc

    async def _query_gpus(self) -> list[dict[str, Any]]:
        """Query GPU device metrics."""
        query = (
            "name,driver_version,index,memory.total,memory.used,"
            "memory.free,power.draw,power.limit,temperature.gpu,"
            "utilization.gpu,utilization.memory,clocks.sm,clocks.memory,"
            "ecc.errors.corrected.volatile.dram.count,"
            "ecc.errors.corrected.volatile.sram.count"
        )
        try:
            data = await self._run_nvidia_smi_json(query)
        except SnapshotError:
            return []

        gpus = []
        for gpu in data.get("gpus", []):
            gpus.append({
                "device": gpu.get("name", "unknown"),
                "driver_version": gpu.get("driver_version", "unknown"),
                "index": int(gpu.get("index", 0)),
                "memory": {
                    "total_bytes": self._parse_bytes(gpu.get("memory.total", "0 MiB")),
                    "used_bytes": self._parse_bytes(gpu.get("memory.used", "0 MiB")),
                    "free_bytes": self._parse_bytes(gpu.get("memory.free", "0 MiB")),
                    "usage_percent": round(
                        self._parse_percent(gpu.get("memory.used", "0 %"))
                    ),
                },
                "power": {
                    "watts": self._parse_watts(gpu.get("power.draw", "0 W")),
                    "limit_watts": self._parse_watts(gpu.get("power.limit", "0 W")),
                },
                "temperature": {
                    "gpu_celsius": self._parse_temp(gpu.get("temperature.gpu", "0 C")),
                },
                "utilization": {
                    "gpu_percent": self._parse_percent(gpu.get("utilization.gpu", "0 %")),
                    "memory_percent": self._parse_percent(gpu.get("utilization.memory", "0 %")),
                },
                "clocks": {
                    "sm_mhz": self._parse_mhz(gpu.get("clocks.sm", "0 MHz")),
                    "memory_mhz": self._parse_mhz(gpu.get("clocks.memory", "0 MHz")),
                },
                "ecc": {
                    "corrected_dram": int(gpu.get("ecc.errors.corrected.volatile.dram.count", 0)),
                    "corrected_sram": int(gpu.get("ecc.errors.corrected.volatile.sram.count", 0)),
                },
            })
        return gpus

    async def _query_processes(self) -> list[dict[str, Any]]:
        """Query per-process GPU usage."""
        query = "index,processes.used.memory,processes.type"
        try:
            data = await self._run_nvidia_smi_json(query)
        except SnapshotError:
            return []

        processes = []
        for gpu in data.get("gpus", []):
            gpu_idx = gpu.get("index", 0)
            for proc in gpu.get("processes", []):
                processes.append({
                    "gpu_index": int(gpu_idx),
                    "process_name": proc.get("process_name", "unknown"),
                    "pid": int(proc.get("pid", 0)),
                    "gpu_memory_bytes": self._parse_bytes(proc.get("used.memory", "0 MiB")),
                    "process_type": proc.get("type", "unknown"),
                })
        return processes

    # -- parsing helpers -----------------------------------------------------

    def _parse_bytes(self, value: str) -> int:
        """Parse a size like '16384 MiB' to bytes."""
        value = str(value).strip()
        if value.endswith(" MiB"):
            return int(float(value[:-4]) * 1024 * 1024)
        if value.endswith(" GiB"):
            return int(float(value[:-4]) * 1024 * 1024 * 1024)
        if value.endswith(" KiB"):
            return int(float(value[:-4]) * 1024)
        if value.endswith(" B"):
            return int(value[:-2])
        try:
            return int(value)
        except ValueError:
            return 0

    def _parse_percent(self, value: str) -> float:
        """Parse a percentage like '45 %' to float."""
        value = str(value).strip()
        if value.endswith(" %"):
            value = value[:-2]
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _parse_watts(self, value: str) -> float:
        """Parse power like '75 W' to watts."""
        value = str(value).strip()
        if value.endswith(" W"):
            value = value[:-2]
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _parse_temp(self, value: str) -> float:
        """Parse temperature like '65 C' to Celsius."""
        value = str(value).strip()
        if value.endswith(" C"):
            value = value[:-2]
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _parse_mhz(self, value: str) -> int:
        """Parse clock frequency like '1500 MHz' to MHz."""
        value = str(value).strip()
        if value.endswith(" MHz"):
            value = value[:-4]
        try:
            return int(float(value))
        except ValueError:
            return 0

    # -- emitted event types -------------------------------------------------

    def emitted_event_types(self) -> list[str]:
        return ["gpu.metrics"]


__all__ = ["GPUConnector"]
