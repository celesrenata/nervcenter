"""Compute node records (NerveCenter spec Section 10-16).

A *ComputeNode* describes a device that can serve inference for NerveCenter
— local (CPU/Neural Engine/Metal GPU), edge, or cloud — and advertises the
models it can host. Routing and telemetry both key off nodes.

Assumptions (spec not present in the repository):
    - ``device_type`` is a classification literal (cpu, gpu, apple_ne,
      metal, tpu, other).
    - ``location`` classifies where the node runs (on_device, local, edge,
      cloud).
    - ``status`` reflects operational state.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Kind of accelerator/device the node offers.
DeviceType = Literal["cpu", "gpu", "apple_ne", "metal", "tpu", "hybrid", "other"]

#: Where the node runs relative to the user.
NodeLocation = Literal["on_device", "local", "edge", "cloud"]

#: Operational state of a compute node.
NodeStatus = Literal["online", "offline", "degraded", "draining"]


class ComputeNode(Record):
    """A device or host that can serve inference workloads."""

    host: str = Field(
        ...,
        description="Host label for the node (machine name or alias).",
    )
    device_type: DeviceType = Field(
        ...,
        description="Primary accelerator class of this node.",
    )
    location: NodeLocation = Field(
        default="local",
        description="Where the node runs relative to the user.",
    )
    status: NodeStatus = Field(
        default="offline",
        description="Current operational state.",
    )
    hardware: str | None = Field(
        default=None,
        description="Model/identifier of the hardware (e.g. 'M3 Max', 'RTX 4090').",
    )
    memory_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Total usable memory in bytes, when known.",
    )
    capacity: dict[str, int] = Field(
        default_factory=dict,
        description="Numeric capacity counters (concurrency, slots) by key.",
    )
    supported_models: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`ModelDescriptor` records this node can serve.",
    )
    last_heartbeat_at: datetime | None = Field(
        default=None,
        description="Last heartbeat from the node (UTC).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific metadata.",
    )
