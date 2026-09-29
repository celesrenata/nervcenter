"""PlannedChange records (NerveCenter spec Section 10-16).

A *PlannedChange* is a proposed modification to NerveCenter state (knowledge
graph, goals, tasks, config, ...) that must be reviewed before execution.
Planned changes are the bridge between inference and execution: nothing
mutates the graph or schedule without a corresponding planned change, either
auto-approved by policy or approved by a human.

Assumptions (spec not present in the repository):
    - ``change_type`` is a classification literal over the kinds of changes
      the core can make.
    - ``risk_level`` is a 0..4 severity scale used by the policy layer to
      decide auto-approve vs human-approve.
    - ``diff`` carries the before/after representation in a JSON-serializable
      envelope; ``rollback`` describes how to revert.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Kind of change being proposed.
ChangeType = Literal[
    "entity_upsert",
    "relationship_upsert",
    "claim_transition",
    "goal_change",
    "task_create",
    "task_cancel",
    "config_update",
    "policy_update",
    "data_deletion",
    "other",
]

#: Lifecycle state of a planned change.
PlannedChangeStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "applied",
    "rolled_back",
    "expired",
]


class PlannedChange(Record):
    """A proposed, reviewable modification to NerveCenter state."""

    change_type: ChangeType = Field(
        ...,
        description="Kind of change being proposed.",
    )
    title: str = Field(..., description="Short human-readable summary of the change.")
    description: str | None = Field(
        default=None,
        description="Full description of what will change and why.",
    )
    status: PlannedChangeStatus = Field(
        default="draft",
        description="Lifecycle state of this planned change.",
    )
    risk_level: int = Field(
        default=1,
        ge=0,
        le=4,
        description="Risk severity; 0 (trivial) to 4 (critical). Policy maps risk to approval policy.",
    )
    subject_ids: list[str] = Field(
        default_factory=list,
        description="Ids of records this change targets (entities, goals, tasks, ...).",
    )
    source_decision_id: str | None = Field(
        default=None,
        description="Id of the :class:`Decision` that produced this change.",
    )
    diff: dict[str, Any] = Field(
        default_factory=dict,
        description="Before/after diff representation of the change.",
    )
    rollback: dict[str, Any] = Field(
        default_factory=dict,
        description="Instructions/payload for reverting this change if applied.",
    )
    proposed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the change was first proposed (UTC).",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="If set, the change is auto-expired (not applied) after this moment.",
    )
    approval_id: str | None = Field(
        default=None,
        description="Id of the :class:`Approval` governing this change, if any.",
    )
