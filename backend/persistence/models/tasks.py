"""Task and TaskRun ORM models mapping :class:`~schemas.tasks.Task` and :class:`~schemas.tasks.TaskRun`.

The ``tasks`` table stores scheduled work units; ``task_runs`` tracks individual
execution attempts. This enables retry semantics and execution history (see
Sections 10-16 of the specification).

Tasks table columns
-------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``title`` (text) — short human-readable title.
- ``description`` (text, nullable) — full description.
- ``status`` (text) — lifecycle (pending|scheduled|in_progress|completed|failed|cancelled).
- ``priority`` (integer) — scheduling priority (0..10).
- ``goal_id`` (UUID, nullable) — parent goal.
- ``decision_id`` (UUID, nullable) — triggering decision.
- ``assignee_agent_id`` (UUID, nullable) — executor agent.
- ``due_at`` (timestamp, nullable) — optional deadline.
- ``scheduled_at`` (timestamp, nullable) — when queued.
- ``inputs`` (JSONB) — structured inputs for the executor.
- ``parent_task_id`` (UUID, nullable) — parent for hierarchical tasks.

TaskRuns table columns
----------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``task_id`` (UUID) — task this run executes.
- ``status`` (text) — outcome (running|succeeded|failed|timed_out|cancelled).
- ``attempt`` (integer) — 1-based attempt number.
- ``started_at`` / ``finished_at`` (timestamp, nullable) — execution window.
- ``agent_id`` (UUID, nullable) — executor agent.
- ``model_id`` (text, nullable) — model used (when applicable).
- ``result_ref`` (UUID, nullable) — produced :class:`~schemas.goals.AgentResult`.
- ``error`` (text, nullable) — failure message.
- ``logs_ref`` (text, nullable) — log reference.

Indexes
-------
- ``ix_tasks_status_priority`` — priority queue ordering.
- ``ix_tasks_goal_id_status`` — goal progress tracking.
- ``ix_task_runs_task_id_attempt`` — attempt ordering.
- ``ix_task_runs_task_id_status`` — execution history by status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Task(Base):
    """ORM mapping of :class:`~schemas.tasks.Task`."""

    __tablename__ = "tasks"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    goal_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    decision_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    assignee_agent_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    parent_task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    dependencies: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_tasks_status_priority_created_at",
            "status",
            "priority",
            "created_at",
        ),
        Index(
            "ix_tasks_goal_id_status_created_at",
            "goal_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_tasks_scheduled_at_status",
            "scheduled_at",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id!r} title={self.title!r} status={self.status!r}>"


class TaskRun(Base):
    """ORM mapping of :class:`~schemas.tasks.TaskRun`."""

    __tablename__ = "task_runs"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    attempt: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    model_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    result_ref: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    logs_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index(
            "ix_task_runs_task_id_attempt",
            "task_id",
            "attempt",
        ),
        Index(
            "ix_task_runs_task_id_status",
            "task_id",
            "status",
        ),
        Index(
            "ix_task_runs_model_id_status",
            "model_id",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<TaskRun id={self.id!r} task_id={self.task_id!r} attempt={self.attempt} status={self.status!r}>"
