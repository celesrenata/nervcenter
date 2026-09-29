"""Data models for the NerveCenter API."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Status(StrEnum):
    """Service status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ServiceHealth(BaseModel):
    """Health check result for a service."""
    name: str
    status: Status
    version: str | None = None
    message: str | None = None
    details: dict[str, Any] | None = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: Status
    services: list[ServiceHealth]
    total_services: int
    healthy_services: int


class MetricsPoint(BaseModel):
    """Single metrics data point."""
    timestamp: datetime
    name: str
    value: float
    labels: dict[str, str] | None = None


class MetricsResponse(BaseModel):
    """Metrics response."""
    metrics: list[MetricsPoint]
    summary: dict[str, Any] | None = None


class TraceSpan(BaseModel):
    """Trace span representation."""
    span_id: str
    trace_id: str
    operation: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str
    attributes: dict[str, Any] | None = None
    parent_span_id: str | None = None


class TraceResponse(BaseModel):
    """Trace response."""
    trace_id: str
    spans: list[TraceSpan]
    root_span: TraceSpan | None = None


class AuthRequest(BaseModel):
    """Authentication request."""
    username: str
    password: str


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int
    user: dict[str, Any]


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class ErrorDetail(BaseModel):
    """Error detail."""
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail
    request_id: str


class VersionInfo(BaseModel):
    """API version information."""
    version: str
    release_date: str | None = None
    compatible_versions: list[str] = []


class ApiResponseMeta(BaseModel):
    """API response metadata."""
    version: str
    request_id: str
    timestamp: datetime
    pagination: dict[str, int] | None = None


class ListResponse(BaseModel):
    """Generic list response."""
    data: list[Any]
    meta: ApiResponseMeta
