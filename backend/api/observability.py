"""Observability endpoints for the NerveCenter API."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.api.models import (
    HealthResponse,
    MetricsPoint,
    MetricsResponse,
    ServiceHealth,
    Status,
    TraceResponse,
    TraceSpan,
)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Get health status of all services."""
    # In a real implementation, this would query actual service health
    services = [
        ServiceHealth(
            name="core",
            status=Status.HEALTHY,
            version="1.0.0",
            message="Service is operational",
        ),
        ServiceHealth(
            name="database",
            status=Status.HEALTHY,
            version="2.1.0",
            message="Database connection established",
        ),
        ServiceHealth(
            name="cache",
            status=Status.DEGRADED,
            version="1.2.3",
            message="Cache performance degraded",
        ),
    ]

    healthy_count = sum(1 for s in services if s.status == Status.HEALTHY)

    return HealthResponse(
        status=Status.HEALTHY if healthy_count == len(services) else Status.DEGRADED,
        services=services,
        total_services=len(services),
        healthy_services=healthy_count,
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get system metrics."""
    # In a real implementation, this would collect actual metrics
    metrics = [
        MetricsPoint(
            timestamp=datetime.utcnow(),
            name="cpu_usage",
            value=45.6,
            labels={"host": "server1"},
        ),
        MetricsPoint(
            timestamp=datetime.utcnow(),
            name="memory_usage",
            value=78.2,
            labels={"host": "server1"},
        ),
        MetricsPoint(
            timestamp=datetime.utcnow(),
            name="request_rate",
            value=123.4,
            labels={"service": "api"},
        ),
    ]

    return MetricsResponse(
        metrics=metrics,
        summary={
            "total_metrics": len(metrics),
            "latest_timestamp": max(m.timestamp for m in metrics).isoformat(),
        },
    )


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str):
    """Get trace information for a specific trace ID."""
    # In a real implementation, this would query actual trace data
    if trace_id != "valid-trace-id":
        raise HTTPException(status_code=404, detail="Trace not found")

    spans = [
        TraceSpan(
            span_id="span-1",
            trace_id=trace_id,
            operation="api_request",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=123.45,
            status="ok",
            attributes={"http.method": "GET", "http.url": "/health"},
        ),
        TraceSpan(
            span_id="span-2",
            trace_id=trace_id,
            operation="database_query",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=45.67,
            status="ok",
            attributes={"db.statement": "SELECT * FROM users"},
            parent_span_id="span-1",
        ),
    ]

    return TraceResponse(
        trace_id=trace_id,
        spans=spans,
        root_span=spans[0] if spans else None,
    )
