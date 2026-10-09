"""Temporal relationship management for the knowledge plane.

:class:`RelationshipService` owns the ``relationships`` table: CRUD plus
temporal-window queries, per NerveCenter Section 13 (Temporal Relationships).

Window model
------------
Every relationship carries a half-open validity window ``[valid_from, valid_to)``:

- ``valid_from=None`` — no lower bound ("all-time").
- ``valid_to=None`` — no upper bound (still active).

A relationship is *active at* instant ``t`` when
``(valid_from is None or valid_from <= t)`` and
``(valid_to is None or valid_to > t)``.

Storage note
------------
The v0 ORM model declares ``valid_from``/``valid_to``/``asserted_at`` as
``String`` columns carrying ISO-8601 values (the Alembic migration defines
them as ``timestamptz``); we normalize every write to ISO-8601 strings so
lexicographic comparison in SQL agrees with chronological semantics for
either schema.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.persistence.models import Entity as EntityORM
from backend.persistence.models import Relationship as RelationshipORM
from schemas.base import TemporalWindow
from schemas.relationships import Relationship as RelationshipSchema

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Temporal value helpers
# ---------------------------------------------------------------------------


def _utc(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is tz-aware UTC (``None`` passthrough)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _parse(value: str | datetime | None) -> datetime | None:
    """Coerce an ORM temporal value (ISO string or datetime) to a UTC datetime.

    The v0 ORM model declares the temporal columns as ``String`` but the
    Alembic migration creates ``timestamptz``; asyncpg may hand us either
    shape, so normalize both.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    raise TypeError(f"unsupported temporal value: {type(value).__name__}")


def _orm_to_schema(orm: RelationshipORM) -> RelationshipSchema:
    """Project an ORM relationship onto the v0 pydantic schema."""
    asserted = _parse(orm.asserted_at)
    return RelationshipSchema(
        id=str(orm.id),
        created_at=orm.created_at,
        schema_version=orm.schema_version or "v0",
        hash=orm.hash,
        source_entity_id=str(orm.source_entity_id),
        target_entity_id=str(orm.target_entity_id),
        relation_type=orm.relation_type,  # type: ignore[arg-type]
        properties=dict(orm.properties or {}),
        valid=TemporalWindow(valid_from=_parse(orm.valid_from), valid_to=_parse(orm.valid_to)),
        asserted_at=asserted or datetime.now(UTC),
        confidence=float(orm.confidence or 1.0),
        evidence=list(orm.evidence or []),
    )


def _schema_to_orm(schema: RelationshipSchema) -> RelationshipORM:
    """Project the v0 pydantic schema onto the ORM row."""
    return RelationshipORM(
        id=schema.id,
        created_at=schema.created_at,
        schema_version=schema.schema_version or "v0",
        hash=schema.fingerprint() if schema.hash is None else schema.hash,
        source_entity_id=schema.source_entity_id,
        target_entity_id=schema.target_entity_id,
        relation_type=schema.relation_type,
        properties=dict(schema.properties or {}),
        valid_from=_utc(schema.valid.valid_from),
        valid_to=_utc(schema.valid.valid_to),
        asserted_at=_utc(schema.asserted_at),
        confidence=float(schema.confidence),
        evidence=list(schema.evidence or []),
    )


def _active_clause(instant: datetime) -> Any:
    """SQL clause: the window of the row covers instant ``instant``."""
    lower = or_(
        RelationshipORM.valid_from.is_(None), RelationshipORM.valid_from <= instant
    )
    upper = or_(
        RelationshipORM.valid_to.is_(None), RelationshipORM.valid_to > instant
    )
    return and_(lower, upper)


class UnknownEntityError(Exception):
    """Raised when a relationship would reference an entity that does not exist."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"relationship references unknown entity id(s): {missing}")
        self.missing = list(missing)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RelationshipService:
    """Async service over the ``relationships`` table (temporal windows).

    Mirrors :class:`~backend.knowledge.entity.EntityService`: writes run in
    their own transaction and results are returned as pydantic schema
    objects, decoupling callers from the ORM layer.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory

    # -- plumbing -----------------------------------------------------------

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            from backend.persistence.connection import make_session_factory

            return make_session_factory(self._engine)
        return self._session_factory

    async def _load(self, session: AsyncSession, rel_id: str) -> RelationshipORM:
        orm = await session.get(RelationshipORM, rel_id)
        if orm is None:
            raise KeyError(f"relationship {rel_id!r} not found")
        return orm

    # -- CRUD ----------------------------------------------------------------

    async def create(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        *,
        properties: dict[str, Any] | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        asserted_at: datetime | None = None,
        confidence: float = 1.0,
        evidence: list[str] | None = None,
    ) -> RelationshipSchema:
        """Create a relationship between two existing entities.

        Raises :class:`UnknownEntityError` if either endpoint is missing and
        ``ValueError`` for an inverted window (``valid_from > valid_to``).
        """
        wf, wt = _utc(valid_from), _utc(valid_to)
        if wf is not None and wt is not None and wf > wt:
            raise ValueError("valid_from must not be after valid_to")
        schema = RelationshipSchema(
            id=str(uuid4()),
            source_entity_id=source_id,
            target_entity_id=target_id,
            relation_type=relation_type,
            properties=dict(properties or {}),
            valid=TemporalWindow(valid_from=valid_from, valid_to=valid_to),
            asserted_at=asserted_at or datetime.now(UTC),
            confidence=confidence,
            evidence=list(evidence or []),
        )
        async with self._factory()() as session:
            known = (
                await session.execute(
                    select(EntityORM.id).where(EntityORM.id.in_([source_id, target_id]))
                )
            ).scalars().all()
            known_set = set(known)
            if len(known_set) < 2:
                await session.rollback()
                missing = [i for i in (source_id, target_id) if i not in known_set]
                raise UnknownEntityError(missing)
            orm = _schema_to_orm(schema)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            log.info(
                "knowledge.relationship.created",
                relationship_id=str(orm.id),
                relation_type=orm.relation_type,
            )
            return _orm_to_schema(orm)

    async def get(self, rel_id: str) -> RelationshipSchema:
        """Fetch one relationship by id (``KeyError`` when absent)."""
        async with self._factory()() as session:
            return _orm_to_schema(await self._load(session, rel_id))

    async def update(self, rel_id: str, changes: dict[str, Any]) -> RelationshipSchema:
        """Apply a partial update, merging ``changes`` into the current record.

        ``id`` and ``created_at`` are immutable. ``valid``/``properties`` may
        be replaced wholesale (schema-level fields).
        """
        if "id" in changes or "created_at" in changes:
            raise ValueError("id and created_at are immutable")
        async with self._factory()() as session:
            orm = await self._load(session, rel_id)
            current = _orm_to_schema(orm)
            # Re-validate the merged record (model_copy would skip validation).
            merged = RelationshipSchema.model_validate(
                {**current.model_dump(mode="python"), **changes}
            )
            orm.relation_type = merged.relation_type
            orm.properties = dict(merged.properties or {})
            orm.valid_from = _utc(merged.valid.valid_from)
            orm.valid_to = _utc(merged.valid.valid_to)
            # merged.asserted_at is required by the schema (non-None); quiet pyright.
            orm.asserted_at = _utc(merged.asserted_at)  # type: ignore[assignment]
            orm.confidence = float(merged.confidence)
            orm.evidence = list(merged.evidence or [])
            orm.source_entity_id = merged.source_entity_id
            orm.target_entity_id = merged.target_entity_id
            orm.hash = merged.fingerprint()
            await session.commit()
            await session.refresh(orm)
            log.info("knowledge.relationship.updated", relationship_id=rel_id)
            return _orm_to_schema(orm)

    async def set_properties(
        self, rel_id: str, properties: dict[str, Any] | None
    ) -> RelationshipSchema:
        """Replace the ``properties`` payload of a relationship."""
        async with self._factory()() as session:
            orm = await self._load(session, rel_id)
            orm.properties = dict(properties or {})
            orm.hash = None
            await session.commit()
            await session.refresh(orm)
            return _orm_to_schema(orm)

    async def delete(self, rel_id: str) -> None:
        """Delete one relationship."""
        async with self._factory()() as session:
            orm = await self._load(session, rel_id)
            await session.delete(orm)
            await session.commit()
            log.info("knowledge.relationship.deleted", relationship_id=rel_id)

    # -- window maintenance ---------------------------------------------------

    async def close(self, rel_id: str, at: datetime | None = None) -> RelationshipSchema:
        """Close the validity window at ``at`` (default: now).

        Idempotent: closing a relationship whose window already ended at or
        after ``at`` is a no-op. Closing *before* ``valid_from`` is an error.
        """
        when = _utc(at or datetime.now(UTC))
        assert when is not None
        async with self._factory()() as session:
            orm = await self._load(session, rel_id)
            cur = orm.valid_to
            if cur is not None and cur >= when:
                return _orm_to_schema(orm)
            wf_raw = orm.valid_from
            if wf_raw is not None and wf_raw > when:
                await session.rollback()
                raise ValueError("cannot close a relationship before it began")
            orm.valid_to = when
            await session.commit()
            await session.refresh(orm)
            log.info("knowledge.relationship.closed", relationship_id=rel_id, at=when)
            return _orm_to_schema(orm)

    async def repoint(
        self,
        rel_id: str,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
    ) -> None:
        """Re-point the endpoints of a relationship (used by entity merging)."""
        if source_id is None and target_id is None:
            raise ValueError("repoint requires source_id and/or target_id")
        async with self._factory()() as session:
            orm = await self._load(session, rel_id)
            if source_id is not None:
                orm.source_entity_id = source_id
            if target_id is not None:
                orm.target_entity_id = target_id
            orm.hash = None
            await session.commit()

    # -- temporal queries -----------------------------------------------------

    async def active_at(
        self,
        entity_id: str,
        at: datetime | None = None,
        *,
        direction: str = "outgoing",
        relation_types: Sequence[str] | None = None,
        limit: int = 200,
    ) -> list[RelationshipSchema]:
        """All relationships touching ``entity_id`` that are active at ``at``.

        ``direction`` selects which side the entity is on: ``outgoing``
        (default), ``incoming`` or ``both``.
        """
        if direction not in ("outgoing", "incoming", "both"):
            raise ValueError(f"unknown direction {direction!r}")
        instant = _utc(at or datetime.now(UTC))
        assert instant is not None
        stmt = select(RelationshipORM).where(_active_clause(instant))
        if direction == "outgoing":
            stmt = stmt.where(RelationshipORM.source_entity_id == entity_id)
        elif direction == "incoming":
            stmt = stmt.where(RelationshipORM.target_entity_id == entity_id)
        else:
            stmt = stmt.where(
                or_(
                    RelationshipORM.source_entity_id == entity_id,
                    RelationshipORM.target_entity_id == entity_id,
                )
            )
        if relation_types is not None:
            stmt = stmt.where(RelationshipORM.relation_type.in_(list(relation_types)))
        stmt = stmt.order_by(RelationshipORM.asserted_at.desc()).limit(limit)
        async with self._factory()() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def between(
        self,
        source_id: str,
        target_id: str,
        at: datetime | None = None,
        *,
        relation_type: str | None = None,
    ) -> list[RelationshipSchema]:
        """Relationships from ``source_id`` to ``target_id`` active at ``at``."""
        instant = _utc(at or datetime.now(UTC))
        assert instant is not None
        stmt = select(RelationshipORM).where(
            _active_clause(instant),
            RelationshipORM.source_entity_id == source_id,
            RelationshipORM.target_entity_id == target_id,
        )
        if relation_type is not None:
            stmt = stmt.where(RelationshipORM.relation_type == relation_type)
        async with self._factory()() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def overlapping(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        window_from: datetime | None = None,
        window_to: datetime | None = None,
        limit: int = 500,
    ) -> list[RelationshipSchema]:
        """Relationships whose validity window overlaps ``[window_from, window_to)``.

        A row ``r`` overlaps the query window when
        ``(r.valid_from IS NULL OR r.valid_from < window_to)`` AND
        ``(r.valid_to IS NULL OR r.valid_to > window_from)``. Omitting both
        window bounds matches rows of any window (bounded by ``limit``).
        """
        conds: list[Any] = []
        wt = _utc(window_to)
        wf = _utc(window_from)
        if wt is not None:
            conds.append(
                or_(
                    RelationshipORM.valid_from.is_(None),
                    RelationshipORM.valid_from < wt,
                )
            )
        if wf is not None:
            conds.append(
                or_(
                    RelationshipORM.valid_to.is_(None),
                    RelationshipORM.valid_to > wf,
                )
            )
        stmt = select(RelationshipORM).where(*conds) if conds else select(RelationshipORM)
        if source_id is not None:
            stmt = stmt.where(RelationshipORM.source_entity_id == source_id)
        if target_id is not None:
            stmt = stmt.where(RelationshipORM.target_entity_id == target_id)
        if relation_type is not None:
            stmt = stmt.where(RelationshipORM.relation_type == relation_type)
        stmt = stmt.order_by(RelationshipORM.asserted_at).limit(limit)
        async with self._factory()() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def timeline(
        self,
        *,
        entity_id: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 500,
    ) -> list[RelationshipSchema]:
        """All-time edges (regardless of window), in assertion order.

        The basis for time-travel: combine with :meth:`active_at` to
        reconstruct past states, or with :meth:`close` to end an edge.
        """
        conds: list[Any] = []
        if entity_id is not None:
            conds.append(
                or_(
                    RelationshipORM.source_entity_id == entity_id,
                    RelationshipORM.target_entity_id == entity_id,
                )
            )
        if source_id is not None:
            conds.append(RelationshipORM.source_entity_id == source_id)
        if target_id is not None:
            conds.append(RelationshipORM.target_entity_id == target_id)
        if relation_type is not None:
            conds.append(RelationshipORM.relation_type == relation_type)
        stmt = select(RelationshipORM).where(*conds) if conds else select(RelationshipORM)
        stmt = stmt.order_by(RelationshipORM.asserted_at).limit(limit)
        async with self._factory()() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def active_snapshot(
        self,
        at: datetime | None = None,
        *,
        relation_types: Sequence[str] | None = None,
        limit: int = 20_000,
    ) -> list[RelationshipSchema]:
        """Every relationship active at ``at`` (default: now).

        Used by time-travel and derivation to load a consistent view of the
        graph at one instant.
        """
        instant = _utc(at or datetime.now(UTC))
        assert instant is not None
        stmt = select(RelationshipORM).where(_active_clause(instant))
        if relation_types is not None:
            stmt = stmt.where(RelationshipORM.relation_type.in_(list(relation_types)))
        stmt = stmt.order_by(RelationshipORM.asserted_at).limit(limit)
        async with self._factory()() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]
