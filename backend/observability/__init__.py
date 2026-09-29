"""Observability module for NerveCenter.

This module provides OpenTelemetry span wiring and Prometheus metrics
per spec §74, correlating:

- Request
- Context compile
- Planning
- Task DAG
- Agent execution
- Inference
- Verification
- Response

Spec sections
-------------
- NerveCenter specification Section 74 (Observability).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from prometheus_client import Counter, Gauge, Histogram, start_http_server

log = structlog.get_logger(__name__)

__all__ = [
    "init_tracer",
    "get_tracer",
    "start_span",
    "Observability",
    " Metrics",
]


class Metrics:
    """Prometheus metrics for NerveCenter."""

    def __init__(self, port: int = 9090) -> None:
        self.port = port
        self._started = False

        # Request counters
        self.requests_total = Counter(
            "nervcenter_requests_total",
            "Total number of requests",
            ["endpoint", "method"],
        )
        self.requests_failed = Counter(
            "nervcenter_requests_failed",
            "Number of failed requests",
            ["endpoint", "method", "error_type"],
        )

        # Operation histograms
        self.request_duration = Histogram(
            "nervcenter_request_duration_seconds",
            "Request duration in seconds",
            ["endpoint", "method"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

        # Agent metrics
        self.agent_runs_total = Counter(
            "nervcenter_agent_runs_total",
            "Total number of agent runs",
            ["agent_type", "status"],
        )

        self.agent_duration = Histogram(
            "nervcenter_agent_duration_seconds",
            "Agent run duration in seconds",
            ["agent_type"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
        )

        # Inference metrics
        self.inference_calls = Counter(
            "nervcenter_inference_calls_total",
            "Total number of inference calls",
            ["model", "provider"],
        )

        self.inference_latency = Histogram(
            "nervcenter_inference_latency_seconds",
            "Inference latency in seconds",
            ["model", "provider"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

        # Pipeline stages
        self.context_compile_duration = Histogram(
            "nervcenter_context_compile_duration_seconds",
            "Context compilation duration in seconds",
            ["stage"],
        )

        self.planning_duration = Histogram(
            "nervcenter_planning_duration_seconds",
            "Planning duration in seconds",
        )

        self.verification_duration = Histogram(
            "nervcenter_verification_duration_seconds",
            "Verification duration in seconds",
            ["result"],
        )

    def start(self) -> None:
        """Start the Prometheus metrics server."""
        if self._started:
            return
        start_http_server(self.port)
        self._started = True
        log.info("prometheus.metrics_server_started", port=self.port)

    def stop(self) -> None:
        """Stop the Prometheus metrics server."""
        # In production, you might want to properly shutdown
        self._started = False


class Observability:
    """OpenTelemetry + Prometheus observability handler."""

    def __init__(self, metrics_port: int = 9090) -> None:
        self.tracer = trace.get_tracer("nervcenter")
        self.metrics = Metrics(port=metrics_port)

    def init(self) -> None:
        """Initialize tracing and metrics."""
        # Setup tracing
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer("nervcenter")

        # Setup metrics
        self.metrics.start()

        log.info("observability.initialized")

    @asynccontextmanager
    async def span(self, name: str, **attributes: Any):
        """Context manager for creating spans."""
        with self.tracer.start_as_current_span(name, attributes) as span:
            yield span

    async def record_request(
        self, endpoint: str, method: str, duration: float, success: bool
    ) -> None:
        """Record a request metric."""
        if success:
            self.metrics.requests_total.labels(endpoint, method).inc()
        else:
            self.metrics.requests_failed.labels(endpoint, method, "unknown").inc()

        self.metrics.request_duration.labels(endpoint, method).observe(duration)

    async def record_agent_run(
        self, agent_type: str, duration: float, status: str
    ) -> None:
        """Record an agent run metric."""
        self.metrics.agent_runs_total.labels(agent_type, status).inc()
        self.metrics.agent_duration.labels(agent_type).observe(duration)

    async def record_inference(
        self, model: str, provider: str, latency: float, success: bool = True
    ) -> None:
        """Record an inference metric."""
        if success:
            self.metrics.inference_calls.labels(model, provider).inc()
            self.metrics.inference_latency.labels(model, provider).observe(latency)

    async def record_context_compile(
        self, stage: str, duration: float
    ) -> None:
        """Record a context compilation metric."""
        self.metrics.context_compile_duration.labels(stage).observe(duration)

    async def record_planning(self, duration: float) -> None:
        """Record a planning metric."""
        self.metrics.planning_duration.observe(duration)

    async def record_verification(
        self, result: str, duration: float
    ) -> None:
        """Record a verification metric."""
        self.metrics.verification_duration.labels(result).observe(duration)


# Global observability instance
_observability: Observability | None = None


def init_tracer() -> None:
    """Initialize the global tracer."""
    global _observability
    _observability = Observability()
    _observability.init()


def get_tracer():
    """Get the global tracer."""
    global _observability
    if _observability is None:
        init_tracer()
    return _observability.tracer


@asynccontextmanager
async def start_span(name: str, **attributes: Any):
    """Start a new span."""
    global _observability
    if _observability is None:
        init_tracer()
    async with _observability.span(name, **attributes) as span:
        yield span
