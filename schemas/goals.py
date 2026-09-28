"""Goal and AgentResult records (NerveCenter spec Section 10-16).

A *goal* is a desired state the core works toward, optionally decomposed into
subgoals and expressed against measurable criteria. An *agent result* is the
structured output of an agent/task execution.

Assumptions (spec not present in the repository):
    - ``Goal.status`` reflects the goal lifecycle; ``progress`` is 0..1.
    - Subgoals reference other goal ids via ``subgoal_ids`` (graph-like).
    - ``AgentResult`` links back to the ``task_run_id`` that produced it and
      carries an optional ``structured_output`` payload.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Lifecycle state of a goal.
GoalStatus = Literal["active", "paused", "achieved", "abandoned"]

#: Outcome status of an agent execution.
AgentResultStatus = Literal["succeeded", "failed", "partial", "needs_approval"]


class Goal(Record):
    """A desired state the core works toward, with measurable criteria."""

    title: str = Field(..., description="Short statement of the goal.")
    description: str | None = Field(
        default=None,
        description="Full description of the goal and its intent.",
    )
    status: GoalStatus = Field(
        default="active",
        description="Lifecycle state of the goal.",
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall progress toward completion (0..1).",
    )
    criteria: list[str] = Field(
        default_factory=list,
        description="Measurable criteria that define completion.",
    )
    subgoal_ids: list[str] = Field(
        default_factory=list,
        description="Ids of child :class:`Goal` records this goal decomposes into.",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Goal priority; 0 (lowest) to 10 (highest).",
    )
    deadline: datetime | None = Field(
        default=None,
        description="Optional deadline for the goal (UTC).",
    )
    related_entity_ids: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Entity` records the goal concerns.",
    )


class AgentResult(Record):
    """Structured output produced by an agent/task execution."""

    task_run_id: str = Field(
        ...,
        description="Id of the :class:`TaskRun` that produced this result.",
    )
    agent_id: str | None = Field(
        default=None,
        description="Id of the agent that produced the result.",
    )
    status: AgentResultStatus = Field(
        default="succeeded",
        description="Outcome status of the execution.",
    )
    summary: str | None = Field(
        default=None,
        description="Human-readable summary of what was accomplished.",
    )
    structured_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed, machine-readable output produced by the agent.",
    )
    produced_entity_ids: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Entity` records created or updated.",
    )
    produced_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records created by the run.",
    )
    produced_claim_ids: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Claim` records produced by the run.",
    )
    cost: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional cost (in USD) of the execution, if tracked.",
    )
    tokens_used: int | None = Field(
        default=None,
        ge=0,
        description="Total tokens consumed, if tracked.",
    )
