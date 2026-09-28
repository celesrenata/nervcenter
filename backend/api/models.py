"""Data models for the NerveCenter API."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Status(str, Enum):
    """Service status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ServiceHealth(BaseModel):
    """Health check result for a service."""
    name: str
    status: Status
    version: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    status: Status
    services: List[ServiceHealth]
    total_services: int
    healthy_services: int


class MetricsPoint(BaseModel):
    """Single metrics data point."""
    timestamp: datetime
    name: str
    value: float
    labels: Optional[Dict[str, str]] = None


class MetricsResponse(BaseModel):
    """Metrics response."""
    metrics: List[MetricsPoint]
    summary: Optional[Dict[str, Any]] = None


class TraceSpan(BaseModel):
    """Trace span representation."""
    span_id: str
    trace_id: str
    operation: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str
    attributes: Optional[Dict[str, Any]] = None
    parent_span_id: Optional[str] = None


class TraceResponse(BaseModel):
    """Trace response."""
    trace_id: str
    spans: List[TraceSpan]
    root_span: Optional[TraceSpan] = None


class AuthRequest(BaseModel):
    """Authentication request."""
    username: str
    password: str


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    user: Dict[str, Any]


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
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail
    request_id: str


class VersionInfo(BaseModel):
    """API version information."""
    version: str
    release_date: Optional[str] = None
    compatible_versions: List[str] = []


class ApiResponseMeta(BaseModel):
    """API response metadata."""
    version: str
    request_id: str
    timestamp: datetime
    pagination: Optional[Dict[str, int]] = None


class ListResponse(BaseModel):
    """Generic list response."""
    data: List[Any]
    meta: ApiResponseMeta