"""Inference route and OmniRoute telemetry records (Section 10-16).

An *InferenceRoute* is the resolved routing decision for one logical request:
which model/ordered fallback chain to try, on which compute nodes, under what
latency/cost constraints. *OmniRouteTelemetry* is the per-provider/per-model
telemetry sample a router (e.g. OmniRoute) attaches so routes can be re-scored
and audited.

Assumptions (spec not present in the repository):
    - ``tier`` is a capability/spending tier literal aligned with common
      OmniRoute tiering (0=free/0.5x Kiro tier, 1=local default, 2=economical,
      3=moderate, 4=high).
    - ``strategy`` records the routing strategy that produced the route
      (auto/latency/cost/quality/forced).
    - ``OmniRouteTelemetry`` captures latency and throughput percentiles plus
      circuit-breaker state.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Capability/spending tier of a route; mirrors OmniRoute's tiering.
RouteTier = Literal[0, 1, 2, 3, 4]

#: Routing strategy that produced or consumes a route.
RouteStrategy = Literal["auto", "latency", "cost", "quality", "forced", "policy"]

#: Circuit-breaker posture reported by the router.
CircuitState = Literal["open", "open_half", "closed"]


class RouteHop(Record):
    """One hop in a route's ordered fallback chain."""

    provider: str = Field(..., description="Provider for this hop.")
    model: str = Field(..., description="Model identifier for this hop.")
    node_id: str | None = Field(
        default=None,
        description="Id of the :class:`ComputeNode` serving this hop, if pinned.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relative weight used when multiple hops are eligible (0..1).",
    )


class InferenceRoute(Record):
    """The resolved routing decision for one logical request."""

    request_key: str = Field(
        ...,
        description="Stable key for the request this route resolves (e.g. a task id or trace id).",
    )
    primary_model: str = Field(
        ...,
        description="The :class:`ModelDescriptor.id` of the first-choice model.",
    )
    primary_provider: str = Field(
        ...,
        description="Provider offering ``primary_model``.",
    )
    tier: RouteTier = Field(
        default=1,
        description="Capability/spending tier the route targets.",
    )
    strategy: RouteStrategy = Field(
        default="auto",
        description="Routing strategy that produced this route.",
    )
    hops: list[RouteHop] = Field(
        default_factory=list,
        description="Ordered fallback hops.",
    )
    latency_budget_ms: float | None = Field(
        default=None,
        ge=1.0,
        description="End-to-end latency budget in milliseconds, if constrained.",
    )
    cost_budget_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Cost budget in USD, if constrained.",
    )
    node_id: str | None = Field(
        default=None,
        description="Id of the :class:`ComputeNode` the route intends, if pinned.",
    )
    status: Literal["pending", "routed", "succeeded", "failed", "exhausted"] = Field(
        default="pending",
        description="Route lifecycle state.",
    )
    resolved_at: datetime | None = Field(
        default=None,
        description="When the route was resolved (UTC).",
    )


class OmniRouteTelemetry(Record):
    """Per (provider, model) latency/throughput/health telemetry sample."""

    provider: str = Field(
        ...,
        description="Provider the telemetry sample is for.",
    )
    model: str = Field(
        ...,
        description="Model identifier the telemetry sample is for.",
    )
    node_id: str | None = Field(
        default=None,
        description="Id of the :class:`ComputeNode` the sample comes from, if any.",
    )
    sample_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the telemetry sample was taken (UTC).",
    )
    requests: int = Field(default=1, ge=0, description="Sampled request count in the window.")
    success_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Fraction of sampled requests that succeeded."
    )
    ttft_ms: float | None = Field(
        default=None, ge=0.0, description="Mean time-to-first-token in milliseconds."
    )
    tokens_per_second: float | None = Field(
        default=None, ge=0.0, description="Mean tokens per second during generation."
    )
    e2e_latency_ms: float | None = Field(
        default=None, ge=0.0, description="Mean end-to-end latency in milliseconds."
    )
    p95_latency_ms: float | None = Field(
        default=None, ge=0.0, description="95th-percentile latency in milliseconds."
    )
    errors: int = Field(
        default=0, ge=0, description="Error count in the sample window."
    )
    circuit_state: CircuitState = Field(
        default="closed",
        description="Circuit-breaker state for this provider/model pair.",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Router-specific counters (cache hit rate, retries, ...).",
    )
