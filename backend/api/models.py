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


class EntityCreateRequest(BaseModel):
    """Request body for creating a new Entity."""
    entity_type: str
    name: str
    description: str | None = None
    attributes: dict[str, Any] = {}
    aliases: list[str] = []
    confidence: float = 1.0
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_evidence: list[str] = []


class EntityUpdateRequest(BaseModel):
    """Request body for updating an Entity."""
    name: str | None = None
    description: str | None = None
    entity_type: str | None = None
    attributes: dict[str, Any] | None = None
    aliases: list[str] | None = None
    confidence: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_evidence: list[str] | None = None


class GoalCreateRequest(BaseModel):
    """Request body for creating a new Goal."""
    title: str
    description: str | None = None
    status: str = "active"
    progress: float = 0.0
    criteria: list[str] = []
    subgoal_ids: list[str] = []
    priority: int = 0
    deadline: datetime | None = None
    related_entity_ids: list[str] = []


class GoalUpdateRequest(BaseModel):
    """Request body for updating a Goal."""
    title: str | None = None
    description: str | None = None
    status: str | None = None
    progress: float | None = None
    criteria: list[str] | None = None
    subgoal_ids: list[str] | None = None
    priority: int | None = None
    deadline: datetime | None = None
    related_entity_ids: list[str] | None = None


class TaskCreateRequest(BaseModel):
    """Request body for creating a new Task."""
    title: str
    description: str | None = None
    status: str = "pending"
    priority: int = 0
    goal_id: str | None = None
    decision_id: str | None = None
    assignee_agent_id: str | None = None
    due_at: datetime | None = None
    scheduled_at: datetime | None = None
    inputs: dict[str, Any] = {}
    dependencies: list[str] = []


class TaskUpdateRequest(BaseModel):
    """Request body for updating a Task."""
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = None
    goal_id: str | None = None
    decision_id: str | None = None
    assignee_agent_id: str | None = None
    due_at: datetime | None = None
    scheduled_at: datetime | None = None
    inputs: dict[str, Any] | None = None
    dependencies: list[str] | None = None


class RelationshipCreateRequest(BaseModel):
    """Request body for creating a new Relationship."""
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    properties: dict[str, Any] = {}
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    evidence: list[str] = []


class ClaimsCreateRequest(BaseModel):
    """Request body for creating a Claim (501 for now)."""
    statement: str
    confidence: float = 1.0
    entity_id: str | None = None

