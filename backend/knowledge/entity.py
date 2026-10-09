"""Entity CRUD service for the NerveCenter knowledge graph.

This module implements :class:`EntityService`, the async CRUD layer over the
``entities`` table. It is the primary entry point for the knowledge plane and
is used by :class:`~backend.knowledge.service.KnowledgeService` as well as by
the resolution, history, and derivation subsystems.

Design notes
------------
- Every mutating method runs inside a single transaction (commit on success,
  rollback on error) via the session factory.
- Temporal validity is expressed through ISO-8601 strings in the ORM layer
  (the ``valid_from``/``valid_to`` columns are ``String`` in the v0 ORM model
  but ``timestamptz`` in the migration); we normalize all input/output to
  ISO-8601 so comparisons are lexicographically correct.
- Records are returned as :class:`~schemas.entities.Entity` (pydantic) so the
  knowledge plane is decoupled from the ORM layer.

Spec sections
-------------
- NerveCenter specification Section 12 (Entity Model).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from backend.persistence.models import Entity as EntityORM
from schemas.base import TemporalWindow
from schemas.entities import Entity as EntitySchema

log = structlog.get_logger(__name__)


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


def _normalize_dt(value: str | datetime | None) -> datetime | None:
    """Coerce an ORM temporal value (ISO string or datetime) to a UTC datetime.

    The v0 ORM model declares ``valid_from``/``valid_to`` as ``String`` columns
    (ISO-8601) but the Alembic migration creates ``timestamptz``; depending on
    which schema is in effect asyncpg may return a string or a datetime, so we
    normalize both shapes here.
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


def _orm_to_schema(orm: EntityORM) -> EntitySchema:
    """Project an ORM entity onto the v0 pydantic schema."""
    valid_from = _normalize_dt(orm.valid_from)
    valid_to = _normalize_dt(orm.valid_to)
    return EntitySchema(
        id=str(orm.id),
        created_at=orm.created_at,
        schema_version=orm.schema_version or "v0",
        hash=orm.hash,
        entity_type=orm.entity_type,  # type: ignore[arg-type]
        name=orm.name,
        description=orm.description,
        attributes=dict(orm.attributes or {}),
        aliases=list(orm.aliases or []),
        confidence=float(orm.confidence or 1.0),
        valid=TemporalWindow(valid_from=valid_from, valid_to=valid_to),
        source_evidence=list(orm.source_evidence or []),
    )


def _schema_to_orm(schema: EntitySchema) -> EntityORM:
    """Project the v0 pydantic schema onto the ORM row (id/created_at preserved)."""
    return EntityORM(
        id=schema.id,
        created_at=schema.created_at,
        schema_version=schema.schema_version or "v0",
        hash=schema.fingerprint() if schema.hash is None else schema.hash,
        entity_type=schema.entity_type,
        name=schema.name,
        description=schema.description,
        attributes=dict(schema.attributes or {}),
        aliases=list(schema.aliases or []),
        confidence=float(schema.confidence),
        valid_from=_utc(schema.valid.valid_from),
        valid_to=_utc(schema.valid.valid_to),
        source_evidence=list(schema.source_evidence or []),
    )


class EntityNotFoundError(Exception):
    """Raised when an entity id does not resolve to a row in the database."""

    def __init__(self, entity_id: str) -> None:
        super().__init__(f"Entity {entity_id!r} not found")
        self.entity_id = entity_id


class EntityConflictError(Exception):
    """Raised on a uniqueness violation for ``(entity_type, name)``."""

    def __init__(self, entity_type: str, name: str) -> None:
        super().__init__(f"Entity of type {entity_type!r} with name {name!r} already exists")
        self.entity_type = entity_type
        self.name = name


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EntityService:
    """Async CRUD service for :class:`~schemas.entities.Entity` records.

    The service owns the transaction boundary for entity writes and returns
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

    # -- internal helpers ----------------------------------------------------

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            from backend.persistence.connection import make_session_factory

            return make_session_factory(self._engine)
        return self._session_factory

    async def _load(self, session: AsyncSession, entity_id: str) -> EntityORM:
        orm = await session.get(EntityORM, entity_id)
        if orm is None:
            raise EntityNotFoundError(entity_id)
        return orm

    # -- CRUD ----------------------------------------------------------------

    async def create(self, payload: dict[str, Any]) -> EntitySchema:
        """Create a new entity from a plain dict payload.

        ``payload`` must contain at minimum ``entity_type`` and ``name``; all
        other fields fall back to their schema defaults. The returned entity
        carries the generated UUID.
        """
        if not payload.get("id"):
            payload = {**payload, "id": str(uuid4())}
        schema = EntitySchema(**payload)

        factory = self._factory()
        async with factory() as session:
            # Uniqueness guard: (entity_type, name) must be unique.
            existing = await session.execute(
                select(EntityORM.id).where(
                    EntityORM.entity_type == schema.entity_type,
                    EntityORM.name == schema.name,
                )
            )
            if existing.first() is not None:
                await session.rollback()
                raise EntityConflictError(schema.entity_type, schema.name)

            orm = _schema_to_orm(schema)
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            log.info(
                "knowledge.entity.created",
                entity_id=str(orm.id),
                entity_type=orm.entity_type,
                name=orm.name,
            )
            return _orm_to_schema(orm)

    async def get(self, entity_id: str) -> EntitySchema:
        """Fetch a single entity by id. Raises :class:`EntityNotFoundError`."""
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, entity_id)
            return _orm_to_schema(orm)

    async def update(
        self,
        entity_id: str,
        changes: dict[str, Any],
    ) -> EntitySchema:
        """Apply a partial update to an existing entity.

        The ``changes`` dict may contain any entity field except ``id`` and
        ``created_at`` (both immutable). Unknown keys are rejected by the
        underlying pydantic schema.
        """
        if "id" in changes or "created_at" in changes:
            raise ValueError("id and created_at are immutable")
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, entity_id)
            current = _orm_to_schema(orm)
            # Re-validate the merged record so unknown keys and type errors
            # are rejected by the schema (model_copy would skip validation).
            merged = EntitySchema.model_validate(
                {**current.model_dump(mode="python"), **changes}
            )
            # Re-uniqueness check if name/type changed.
            if merged.name != current.name or merged.entity_type != current.entity_type:
                hit = await session.execute(
                    select(EntityORM.id).where(
                        EntityORM.entity_type == merged.entity_type,
                        EntityORM.name == merged.name,
                        EntityORM.id != entity_id,
                    )
                )
                if hit.first() is not None:
                    await session.rollback()
                    raise EntityConflictError(merged.entity_type, merged.name)

            new_orm = _schema_to_orm(merged)
            orm.entity_type = new_orm.entity_type
            orm.name = new_orm.name
            orm.description = new_orm.description
            orm.attributes = new_orm.attributes
            orm.aliases = new_orm.aliases
            orm.confidence = new_orm.confidence
            orm.valid_from = new_orm.valid_from
            orm.valid_to = new_orm.valid_to
            orm.source_evidence = new_orm.source_evidence
            orm.hash = new_orm.hash
            await session.commit()
            await session.refresh(orm)
            log.info("knowledge.entity.updated", entity_id=entity_id)
            return _orm_to_schema(orm)

    async def delete(self, entity_id: str) -> None:
        """Delete an entity row. Relationships referencing it are the caller's
        responsibility to clean up (or cascade in the DB)."""
        factory = self._factory()
        async with factory() as session:
            orm = await self._load(session, entity_id)
            await session.delete(orm)
            await session.commit()
            log.info("knowledge.entity.deleted", entity_id=entity_id)

    # -- queries --------------------------------------------------------------

    async def find_by_name(
        self,
        name: str,
        entity_type: str | None = None,
    ) -> list[EntitySchema]:
        """Find entities by exact name, optionally filtered by type."""
        factory = self._factory()
        stmt = select(EntityORM).where(EntityORM.name == name)
        if entity_type is not None:
            stmt = stmt.where(EntityORM.entity_type == entity_type)
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def find_by_alias(self, alias: str) -> list[EntitySchema]:
        """Return entities whose ``aliases`` array contains ``alias``.

        Uses PostgreSQL JSONB ``@>`` containment so the GIN index on
        ``aliases`` can accelerate the lookup.
        """
        factory = self._factory()
        stmt = select(EntityORM).where(EntityORM.aliases.contains([alias]))
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def find_by_evidence(self, evidence_id: str) -> list[EntitySchema]:
        """Return entities citing a given evidence id (provenance reverse lookup)."""
        factory = self._factory()
        stmt = select(EntityORM).where(EntityORM.source_evidence.contains([evidence_id]))
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def list_entities(
        self,
        *,
        entity_type: str | None = None,
        active_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntitySchema]:
        """List entities, optionally filtered by type and/or active at a point in time.

        ``active_at`` restricts results to entities whose validity window covers
        that instant (treating ``valid_from``/``valid_to`` as a half-open
        interval when both are set).
        """
        factory = self._factory()
        stmt = select(EntityORM)
        if entity_type is not None:
            stmt = stmt.where(EntityORM.entity_type == entity_type)
        if active_at is not None:
            at = _utc(active_at)
            lower_ok = or_(EntityORM.valid_from.is_(None), EntityORM.valid_from <= at)
            upper_ok = or_(EntityORM.valid_to.is_(None), EntityORM.valid_to > at)
            stmt = stmt.where(lower_ok, upper_ok)
        stmt = stmt.order_by(EntityORM.created_at.desc()).limit(limit).offset(offset)
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    async def batch_get(self, entity_ids: Iterable[str]) -> list[EntitySchema]:
        """Fetch multiple entities in a single query; missing ids are skipped."""
        ids = [i for i in entity_ids if i]
        if not ids:
            return []
        factory = self._factory()
        stmt = select(EntityORM).where(EntityORM.id.in_(ids))
        async with factory() as session:
            result = await session.execute(stmt)
            return [_orm_to_schema(row) for row in result.scalars().all()]

    # -- aliases ---------------------------------------------------------------

    async def add_alias(self, entity_id: str, alias: str) -> EntitySchema:
        """Attach a new alias to an entity (idempotent)."""
        entity = await self.get(entity_id)
        if alias in entity.aliases:
            return entity
        return await self.update(entity_id, {"aliases": [*entity.aliases, alias]})

    async def remove_alias(self, entity_id: str, alias: str) -> EntitySchema:
        """Detach an alias from an entity (no-op if absent)."""
        entity = await self.get(entity_id)
        if alias not in entity.aliases:
            return entity
        return await self.update(
            entity_id, {"aliases": [a for a in entity.aliases if a != alias]}
        )
