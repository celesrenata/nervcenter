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


class AttentionState(StrEnum):
    """Attention lifecycle states (prompt2 section 25).

    ``NOW`` is the highest-visibility bucket (the Now screen); ``RESOLVED``
    items are archived out of the live queue; ``SUPPRESSED`` hides an item the
    user explicitly muted.
    """

    NOW = "NOW"
    TODAY = "TODAY"
    SOON = "SOON"
    WAITING_ON = "WAITING_ON"
    FYI = "FYI"
    SUPPRESSED = "SUPPRESSED"
    RESOLVED = "RESOLVED"


class AttentionItem(BaseModel):
    """An AttentionItem (prompt2 section 20).

    The principal output of the Personal Operations Plane: one ranked,
    explainable thing that needs the user's attention right now. Scoring is
    deterministic and explainable (prompt2 section 21) -- no opaque ML -- so
    ``reason`` and ``why`` answer "why are you showing me this?" (section 22).
    """

    attention_id: str
    reason: str
    priority: float = Field(default=0.0, ge=0.0, le=1.0)
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    due: datetime | None = None
    entities: list[str] = []
    sources: list[str] = []
    suggested_action: str | None = None
    status: AttentionState = AttentionState.NOW
    # Explainability (section 22): the human-readable reasons behind ranking.
    why: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Messages (prompt2 Phase P1)
# ---------------------------------------------------------------------------


class MessageDirection(StrEnum):
    """Which side of the conversation the message came from (prompt2 §76)."""

    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class Message(BaseModel):
    """One ingested message (prompt2 §76 — message ingestion).

    The macOS Personal Relay (``nerve-personal-relay``) posts normalized
    messages here; NerveCenter never touches source message storage directly
    (prompt2 §47). ``peer_identifier`` is the raw contact id (phone number,
    iMessage handle, ...); ``peer_name`` is the *resolved* display name after
    cross-channel person resolution, which may be ``None`` when no person has
    been matched yet.
    """

    message_id: str
    conversation_id: str
    direction: MessageDirection
    peer_identifier: str
    peer_name: str | None = None
    body: str
    channel: str = "imessage"
    timestamp: datetime
    # Provenance: which ingestion source produced this message
    # (prompt2 §49 — retention is per-source).
    source: str = "personal-relay"


class Conversation(BaseModel):
    """A reconstructed message thread (prompt2 §76 — thread reconstruction).

    A conversation is keyed by (peer, channel): one thread per contact per
    channel. ``unread`` counts INBOUND messages not yet acknowledged, which
    drives the AttentionItem the thread can produce (§76 acceptance).
    """

    conversation_id: str
    peer_identifier: str
    peer_name: str | None = None
    channel: str = "imessage"
    message_count: int = 0
    unread: int = 0
    last_body: str | None = None
    last_direction: MessageDirection | None = None
    last_timestamp: datetime | None = None
    attention_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CalendarEvent(BaseModel):
    """A normalized calendar event (prompt2 §42 Calendar Integration).

    NerveCenter never owns the calendar — the events are synced/read-only
    copies from the user's provider (Apple/Google/Microsoft/CalDAV, §42) or
    ingested as normalized entries. The calendar exists to answer
    *availability* questions: availability, appointments, deadlines,
    travel time, meeting prep, follow-up timing (§42), and conflict
    reasoning such as "Dinner tomorrow?" → "I can do after 7:30" (§43).

    ``start``/``end`` are ``None`` for all-day events (``all_day=True``);
    those block the entire calendar day.
    """

    event_id: str
    title: str
    description: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False
    location: str | None = None
    participants: list[str] = Field(default_factory=list)
    reminder_at: datetime | None = None
    source: str = "calendar-sync"
    sync_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Email (prompt2 Phase P0 — Email + Attention)
# ---------------------------------------------------------------------------


class EmailDirection(StrEnum):
    """Which side of the thread the email came from (prompt2 §75)."""

    RECEIVED = "RECEIVED"
    SENT = "SENT"


class EmailMessage(BaseModel):
    """One ingested email (prompt2 §75 — email ingestion).

    The macOS Personal Relay (``nerve-personal-relay``) posts normalized email
    events here; NerveCenter never touches a mailbox (EWS/IMAP) directly
    (prompt2 §47). ``from_address`` is the raw sender address; ``sender_name``
    is the resolved display name, which may be ``None`` when the sender has
    not been matched yet.
    """

    message_id: str
    thread_id: str
    direction: EmailDirection
    from_address: str
    to_address: str
    subject: str
    body: str = ""
    timestamp: datetime
    # Provenance: which ingestion source produced this message
    # (prompt2 §49 — retention is per-source).
    source: str = "personal-relay"


class EmailThread(BaseModel):
    """A reconstructed email thread (prompt2 §75 — thread reconstruction).

    A thread is keyed by (sender, subject): one thread per sender per
    subject line. ``unread`` counts RECEIVED messages not yet acknowledged,
    which drives the AttentionItem the thread can produce (§75 acceptance).
    """

    thread_id: str
    from_address: str
    to_address: str
    sender_name: str | None = None
    subject: str
    message_count: int = 0
    unread: int = 0
    last_body: str | None = None
    last_direction: EmailDirection | None = None
    last_timestamp: datetime | None = None
    attention_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
