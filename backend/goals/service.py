"""Goal lifecycle service for NerveCenter.

This module implements :class:`GoalService`, the async CRUD + lifecycle layer
over the ``goals`` table (NerveCenter specification Sections 20-22). It mirrors
the design of :class:`~backend.knowledge.entity.EntityService`:

- Every mutating method runs inside a single transaction (commit on success,
  rollback on error).
- Records are returned as :class:`~schemas.goals.Goal` (pydantic) so callers
  never see ORM rows.
- Temporal columns are normalized to ISO-8601 strings at the ORM boundary,
  exactly as the knowledge plane does.

Goal lifecycle
--------------
::

    active -> paused   (human pause)
    active -> achieved  (progress reaches 1.0 / all criteria met)
    paused -> active   (resumed)
    active|paused -> abandoned  (terminal)
    achieved | abandoned -> (terminal)

Progress is tracked in ``progress`` (0..1). Callers update it explicitly or let
:meth:`update_progress` recompute it from associated task completion (see
:mod:`backend.goals.reconciliation`).

Spec sections
-------------
- NerveCenter specification Section 20 (Goal Model).
- NerveCenter specification Section 21 (Goal Decomposition).
- NerveCenter specification Section 22 (Progress & Reconciliation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.persistence.models import Goal as GoalORM
from schemas.goals import Goal as GoalSchema

log = structlog.get_logger(__name__)

__all__ = ["GoalService", "GoalNotFoundError"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is tz-aware UTC (``None`` passthrough)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _orm_to_schema(orm: GoalORM) -> GoalSchema:
    """Project an ORM goal onto the v0 pydantic schema."""
    deadline = orm.deadline
    if isinstance(deadline, str):
        try:
            deadline = datetime.fromisoformat(deadline)
        except ValueError:
            deadline = None
    return GoalSchema(
        id=str(orm.id),
        created_at=orm.created_at,
        schema_version=orm.schema_version or "v0",
        hash=orm.hash,
        title=orm.title,
        description=orm.description,
        status=orm.status,  # type: ignore[arg-type]
        progress=float(orm.progress or 0.0),
        criteria=list(orm.criteria or []),
        subgoal_ids=list(orm.subgoal_ids or []),
        priority=int(orm.priority or 0),
        deadline=deadline,
        related_entity_ids=list(orm.related_entity_ids or []),
    )


def _schema_to_orm(schema: GoalSchema) -> GoalORM:
    """Project the v0 pydantic schema onto the ORM row (id/created_at preserved)."""
    return GoalORM(
        id=schema.id,
        created_at=schema.created_at,
        schema_version=schema.schema_version or "v0",
        hash=schema.fingerprint() if schema.hash is None else schema.hash,
        title=schema.title,
        description=schema.description,
        status=schema.status,
        progress=float(schema.progress),
        criteria=list(schema.criteria or []),
        subgoal_ids=list(schema.subgoal_ids or []),
        priority=int(schema.priority),
        deadline=_utc(schema.deadline),
        related_entity_ids=list(schema.related_entity_ids or []),
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GoalNotFoundError(Exception):
    """Raised when a goal id does not resolve to a row in the database."""

    def __init__(self, goal_id: str) -> None:
        super().__init__(f"Goal {goal_id!r} not found")
        self.goal_id = goal_id


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GoalService:
    """Async lifecycle service for :class:`~schemas.goals.Goal` records.

    The service owns the transaction boundary for goal writes and returns
    pydantic schema objects (not ORM rows), so callers do not need to import
    the persistence layer.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory

    # -- internal helpers ---------------------------------------------------

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            from backend.persistence.connection import make_session_factory

            return make_session_factory(self._engine)
        return self._session_factory

    async def _load(self, session: AsyncSession, goal_id: str) -> GoalORM:
        orm = await session.get(GoalORM, goal_id)
        if orm is None:
            raise GoalNotFoundError(goal_id)
        return orm

    # -- CRUD ----------------------------------------------------------------

    async def create(self, payload: dict[str, Any]) -> GoalSchema:
        """Create a new goal from a plain dict payload.

        ``payload`` must contain ``title``; all other fields fall back to their
        schema defaults (including ``criteria``, which defines the measurable
        completion conditions for the goal). The returned goal carries the
        generated UUID.
        """
        if not payload.get("id"):
            payload = {**payload, "id": str(uuid4())}
        schema = GoalSchema(**payload)

        factory = self._factory()
        async with factory() as session:
            orm = _schema_to_orm(schema)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            log.info(
                "goals.created",
                goal_id=str(orm.id),
                title=orm.title,
                criteria=len(orm.criteria or []),
            )
            return _orm_to_schema(orm)

    async def get(self, goal_id: str) -> GoalSchema:
        """Fetch a single goal by id. Raises :class:`GoalNotFoundError`."""
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, goal_id)
            return _orm_to_schema(orm)

    async def update(
        self,
        goal_id: str,
        changes: dict[str, Any],
    ) -> GoalSchema:
        """Apply a partial update to an existing goal.

        The ``changes`` dict may contain any goal field except ``id`` and
        ``created_at`` (both immutable). Unknown keys are rejected by the
        underlying pydantic schema.
        """
        if "id" in changes or "created_at" in changes:
            raise ValueError("id and created_at are immutable")
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, goal_id)
            current = _orm_to_schema(orm)
            merged = GoalSchema.model_validate(
                {**current.model_dump(mode="python"), **changes}
            )
            new_orm = _schema_to_orm(merged)
            orm.title = new_orm.title
            orm.description = new_orm.description
            orm.status = new_orm.status
            orm.progress = new_orm.progress
            orm.criteria = new_orm.criteria
            orm.subgoal_ids = new_orm.subgoal_ids
            orm.priority = new_orm.priority
            orm.deadline = new_orm.deadline
            orm.related_entity_ids = new_orm.related_entity_ids
            orm.hash = new_orm.hash
            await session.commit()
            await session.refresh(orm)
            log.info("goals.updated", goal_id=goal_id)
            return _orm_to_schema(orm)

    async def delete(self, goal_id: str) -> None:
        """Delete a goal row. Associated tasks are the caller's responsibility."""
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, goal_id)
            await session.delete(orm)
            await session.commit()
            log.info("goals.deleted", goal_id=goal_id)

    async def list_goals(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GoalSchema]:
        """List goals, optionally filtered by status.

        Results are ordered by priority (descending) then creation time
        (descending) so the most important, newest goals surface first.
        """
        factory = self._factory()
        stmt = select(GoalORM)
        if status is not None:
            stmt = stmt.where(GoalORM.status == status)
        stmt = stmt.order_by(GoalORM.priority.desc(), GoalORM.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def active_goals(self, *, limit: int = 100) -> list[GoalSchema]:
        """Return all ``active`` goals, priority-ordered."""
        return await self.list_goals(status="active", limit=limit)

    # -- lifecycle transitions ----------------------------------------------

    async def pause(self, goal_id: str) -> GoalSchema:
        """Pause an active goal. Paused goals are excluded from scheduling."""
        return await self._transition(goal_id, to_status="paused")

    async def resume(self, goal_id: str) -> GoalSchema:
        """Resume a paused goal back to active."""
        return await self._transition(goal_id, to_status="active")

    async def achieve(self, goal_id: str) -> GoalSchema:
        """Mark a goal as achieved and set progress to 1.0."""
        updated = await self._transition(goal_id, to_status="achieved")
        if updated.progress < 1.0:
            updated = await self.update(goal_id, {"progress": 1.0})
        return updated

    async def abandon(self, goal_id: str) -> GoalSchema:
        """Mark a goal as abandoned (terminal)."""
        return await self._transition(goal_id, to_status="abandoned")

    async def update_progress(self, goal_id: str, progress: float) -> GoalSchema:
        """Set goal progress explicitly; auto-achieves when progress >= 1.0."""
        progress = max(0.0, min(1.0, progress))
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, goal_id)
            orm.progress = progress
            if progress >= 1.0 and orm.status not in ("achieved", "abandoned"):
                orm.status = "achieved"
            await session.commit()
            await session.refresh(orm)
            log.info("goals.progress", goal_id=goal_id, progress=progress)
            return _orm_to_schema(orm)

    async def add_subgoal(self, goal_id: str, subgoal_id: str) -> GoalSchema:
        """Link a subgoal id onto a parent goal (idempotent)."""
        goal = await self.get(goal_id)
        if subgoal_id in goal.subgoal_ids:
            return goal
        return await self.update(goal_id, {"subgoal_ids": [*goal.subgoal_ids, subgoal_id]})

    async def _transition(self, goal_id: str, *, to_status: str) -> GoalSchema:
        """Validate and apply a goal lifecycle transition."""
        terminal = ("achieved", "abandoned")
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, goal_id)
            current = orm.status
            if current in terminal:
                raise ValueError(
                    f"Goal {goal_id!r} is terminal ({current!r}); cannot transition to {to_status!r}"
                )
            if current == to_status:
                return _orm_to_schema(orm)
            allowed = {
                "active": {"paused", "achieved", "abandoned"},
                "paused": {"active", "abandoned"},
            }
            if to_status not in allowed.get(current, set()):
                raise ValueError(
                    f"Goal {goal_id!r}: cannot transition {current!r} -> {to_status!r}"
                )
            orm.status = to_status
            await session.commit()
            await session.refresh(orm)
            log.info("goals.transition", goal_id=goal_id, from_=current, to=to_status)
            return _orm_to_schema(orm)

    # -- decomposition / progress computation --------------------------------

    async def progress_from_tasks(
        self,
        goal_id: str,
        completed: int,
        total: int,
    ) -> GoalSchema:
        """Recompute goal progress from associated task completion counts.

        Progress is the fraction of tasks for this goal that are in a terminal
        successful state. A total of zero yields progress 0.0 (a goal with no
        tasks has no measurable progress).
        """
        progress = 0.0 if total <= 0 else completed / total
        return await self.update_progress(goal_id, progress)

    async def count_subgoals(self, goal_id: str) -> int:
        """Return the number of direct subgoals referenced by this goal."""
        goal = await self.get(goal_id)
        return len(goal.subgoal_ids)

    async def children(self, goal_id: str) -> list[GoalSchema]:
        """Return the subgoals referenced by this goal (missing ids skipped)."""
        goal = await self.get(goal_id)
        if not goal.subgoal_ids:
            return []
        factory = self._factory()
        stmt = select(GoalORM).where(GoalORM.id.in_(goal.subgoal_ids))
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def is_complete(self, goal_id: str) -> bool:
        """Return ``True`` when the goal's progress has reached 1.0."""
        goal = await self.get(goal_id)
        return goal.progress >= 1.0 or goal.status == "achieved"

    async def goals_with_deadlines_before(
        self,
        when: datetime,
        *,
        limit: int = 100,
    ) -> list[GoalSchema]:
        """Return active goals whose deadline is before ``when``."""
        bound = _utc(when)
        factory = self._factory()
        stmt = (
            select(GoalORM)
            .where(GoalORM.status == "active")
            .where(or_(GoalORM.deadline.is_(None), GoalORM.deadline <= bound))
            .where(GoalORM.deadline.is_not(None))
            .order_by(GoalORM.deadline.asc())
            .limit(limit)
        )
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]
