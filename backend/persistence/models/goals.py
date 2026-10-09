"""Goal and AgentResult ORM models mapping :class:`~schemas.goals.Goal` and :class:`~schemas.goals.AgentResult`.

The ``goals`` table stores desired states the core works toward, optionally
decomposed into subgoals. The ``agent_results`` table stores structured outputs
from agent/task executions (see Sections 10-16 of the specification).

Goals table columns
-------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``title`` (text) — short statement of the goal.
- ``description`` (text, nullable) — full description.
- ``status`` (text) — lifecycle (active|paused|achieved|abandoned).
- ``progress`` (float) — overall progress (0..1).
- ``criteria`` (JSONB array of text) — measurable completion criteria.
- ``subgoal_ids`` (JSONB array of UUID text) — child goal ids.
- ``priority`` (integer) — priority (0..10).
- ``deadline`` (timestamp, nullable) — optional deadline.
- ``related_entity_ids`` (JSONB array of UUID text) — concerned entities.

AgentResults table columns
--------------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``task_run_id`` (UUID) — task run that produced this result.
- ``agent_id`` (UUID, nullable) — producing agent.
- ``status`` (text) — outcome (succeeded|failed|partial|needs_approval).
- ``summary`` (text, nullable) — human-readable summary.
- ``structured_output`` (JSONB) — typed output from the agent.
- ``produced_entity_ids`` / ``produced_evidence_ids`` / ``produced_claim_ids``
  (JSONB arrays) — resulting record ids.
- ``cost`` / ``tokens_used`` (float/int, nullable) — resource tracking.

Indexes
-------
- ``ix_goals_status_priority`` — active goal queue.
- ``ix_goals_status_deadline`` — deadline-aware scheduling.
- ``ix_goals_subgoal_ids_gin`` — subgoal queries (GIN).
- ``ix_agent_results_task_run_id`` — execution trace.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Goal(Base):
    """ORM mapping of :class:`~schemas.goals.Goal`."""

    __tablename__ = "goals"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    progress: Mapped[float] = mapped_column(default=0.0, nullable=False)
    criteria: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)
    subgoal_ids: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)
    priority: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    related_entity_ids: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_goals_status_priority_created_at",
            "status",
            "priority",
            "created_at",
        ),
        Index(
            "ix_goals_status_deadline",
            "status",
            "deadline",
        ),
        Index(
            "ix_goals_subgoal_ids_gin",
            "subgoal_ids",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<Goal id={self.id!r} title={self.title!r} status={self.status!r} progress={self.progress:.1%}>"


class AgentResult(Base):
    """ORM mapping of :class:`~schemas.goals.AgentResult`."""

    __tablename__ = "agent_results"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task_run_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="succeeded", nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    structured_output: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    produced_entity_ids: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    produced_evidence_ids: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    produced_claim_ids: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    cost: Mapped[float | None] = mapped_column(default=None)
    tokens_used: Mapped[int | None] = mapped_column(BigInteger, default=None)

    __table_args__ = (
        Index(
            "ix_agent_results_task_run_id_status",
            "task_run_id",
            "status",
        ),
        Index(
            "ix_agent_results_agent_id_created_at",
            "agent_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentResult id={self.id!r} task_run_id={self.task_run_id!r} status={self.status!r}>"
