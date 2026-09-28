"""NerveCenter v0 core data contracts.

This package defines the Pydantic v2 models for every NerveCenter record type
and interface, corresponding to Sections 10-16 of the NerveCenter specification.

All models derive from :class:`schemas.base.Record`, which provides the common
``id``, ``created_at``, ``schema_version``, and ``hash`` integrity fields.

Modules
-------
- ``events``       — :class:`Event` (Section 10)
- ``entities``     — :class:`Entity` (Section 12)
- ``relationships``— :class:`Relationship` (Section 13)
- ``evidence``     — :class:`Evidence` (Section 15)
- ``claims``       — :class:`Claim`, :class:`Decision` (Section 16)
- ``tasks``        — :class:`Task`, :class:`TaskRun`
- ``goals``        — :class:`Goal`, :class:`AgentResult`
- ``context``      — :class:`ContextPackage`, :class:`ContextSection`
- ``models``       — :class:`ModelDescriptor`
- ``compute``      — :class:`ComputeNode`
- ``routes``       — :class:`InferenceRoute`, :class:`OmniRouteTelemetry`
- ``planned_changes`` — :class:`PlannedChange`
- ``approvals``    — :class:`Approval`
- ``connectors``   — :class:`Connector`
"""

from .approvals import Approval, ApprovalDecision, ApproverType
from .base import SCHEMA_VERSION, Record, TemporalWindow, content_hash
from .claims import Claim, ClaimStatus, Decision, DecisionMechanism
from .compute import (
    ComputeNode,
    DeviceType,
    NodeLocation,
    NodeStatus,
)
from .connectors import (
    Connector,
    ConnectorAuthScheme,
    ConnectorCapability,
    ConnectorStatus,
    ConnectorTransport,
)
from .context import (
    ContextPackage,
    ContextPurpose,
    ContextSection,
    ContextSectionKind,
)
from .entities import Entity, EntityType
from .events import Event, EventCategory, EventSeverity
from .evidence import Evidence, EvidenceSourceType
from .goals import AgentResult, AgentResultStatus, Goal, GoalStatus
from .models import (
    ModelCapability,
    ModelDescriptor,
    ModelModality,
    ModelStatus,
)
from .planned_changes import ChangeType, PlannedChange, PlannedChangeStatus
from .relationships import Relationship, RelationType
from .routes import (
    CircuitState,
    InferenceRoute,
    OmniRouteTelemetry,
    RouteHop,
    RouteStrategy,
    RouteTier,
)
from .tasks import Task, TaskRun, TaskRunStatus, TaskStatus

__all__ = [
    # base
    "SCHEMA_VERSION",
    "Record",
    "TemporalWindow",
    "content_hash",
    # events
    "Event",
    "EventCategory",
    "EventSeverity",
    # entities
    "Entity",
    "EntityType",
    # relationships
    "Relationship",
    "RelationType",
    # evidence
    "Evidence",
    "EvidenceSourceType",
    # claims + decision
    "Claim",
    "ClaimStatus",
    "Decision",
    "DecisionMechanism",
    # tasks
    "Task",
    "TaskRun",
    "TaskStatus",
    "TaskRunStatus",
    # goals + agent results
    "Goal",
    "GoalStatus",
    "AgentResult",
    "AgentResultStatus",
    # context
    "ContextPackage",
    "ContextPurpose",
    "ContextSection",
    "ContextSectionKind",
    # models
    "ModelDescriptor",
    "ModelCapability",
    "ModelModality",
    "ModelStatus",
    # compute
    "ComputeNode",
    "DeviceType",
    "NodeLocation",
    "NodeStatus",
    # routes
    "InferenceRoute",
    "RouteHop",
    "RouteStrategy",
    "RouteTier",
    "OmniRouteTelemetry",
    "CircuitState",
    # planned changes
    "PlannedChange",
    "ChangeType",
    "PlannedChangeStatus",
    # approvals
    "Approval",
    "ApproverType",
    "ApprovalDecision",
    # connectors
    "Connector",
    "ConnectorCapability",
    "ConnectorTransport",
    "ConnectorAuthScheme",
    "ConnectorStatus",
]
