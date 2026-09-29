"""Unified knowledge-plane service facade.

:class:`KnowledgeService` is the high-level, single-entry object that the rest
of NerveCenter (the API surface, MCP server, CLI, web UI) talks to for the
knowledge plane. It wires the individual subsystems together — entity CRUD,
temporal relationships, entity resolution, time-travel + lineage, and
derivation rules — so that callers do not have to manage the persistence
session or remember to record lineage for every mutation.

Design
------
- Subsystems share one :class:`~sqlalchemy.ext.asyncio.AsyncEngine` / session
  factory; the facade owns their lifecycle.
- Every entity mutation (create / update / delete / merge) is recorded into
  a :class:`~backend.knowledge.history.LineageTracker` so past state can
  always be reconstructed.
- The facade is deliberately *thin*: it delegates to the subsystems and
  adds the cross-cutting concerns (lineage, derivation-on-write) in one
  place. Individual subsystems stay independently testable.

Spec sections
-------------
- NerveCenter specification Section 12 (Entity Model).
- NerveCenter specification Section 13 (Temporal Relationships).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from schemas.entities import Entity as EntitySchema
from schemas.relationships import Relationship as RelationshipSchema

from .derivation import DEFAULT_RULES, DerivationEngine, DerivationResult, DerivationRule
from .entity import EntityConflictError, EntityNotFoundError, EntityService
from .history import GraphState, LineageEvent, LineageTracker, StateDiff, TimeTravelQuery
from .relationship import RelationshipService, UnknownEntityError
from .resolution import EntityResolver, MatchCandidate, MergeResult

__all__ = [
    "KnowledgeService",
    # re-exported for convenience
    "EntityService",
    "RelationshipService",
    "EntityResolver",
    "TimeTravelQuery",
    "LineageTracker",
    "DerivationEngine",
    "DerivationRule",
    "DEFAULT_RULES",
    # result types
    "GraphState",
    "StateDiff",
    "DerivationResult",
    "MergeResult",
    "MatchCandidate",
    # errors
    "EntityNotFoundError",
    "EntityConflictError",
    "UnknownEntityError",
]


class KnowledgeService:
    """Facade over the knowledge plane (entities, relationships, resolution,
    time-travel, lineage, derivation).

    Construct with a live persistence engine/session factory. All query
    methods are async.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        lineage: LineageTracker | None = None,
        derivation_rules: Sequence[DerivationRule] | None = None,
    ) -> None:
        self._engine = engine
        self._factory = session_factory

        # Core subsystems (share the engine/factory).
        self.entities = EntityService(engine, session_factory)
        self.relationships = RelationshipService(engine, session_factory)

        # Cross-cutting state.
        self._lineage = lineage or LineageTracker()
        self.resolver = EntityResolver(
            self.entities, self.relationships, lineage=self._lineage
        )
        self.time_travel = TimeTravelQuery(self.entities, self.relationships)
        self.derivation = DerivationEngine(
            self.relationships,
            rules=list(derivation_rules) if derivation_rules else None,
        )

    # -- lifecycle / config --------------------------------------------------

    @property
    def lineage(self) -> LineageTracker:
        """The :class:`LineageTracker` used for entity mutation history."""
        return self._lineage

    def add_derivation_rule(self, rule: DerivationRule) -> None:
        """Register an additional derivation rule with the engine."""
        self.derivation.add_rule(rule)

    # =========================================================================
    # ENTITY CRUD (with lineage)
    # =========================================================================

    async def create_entity(self, payload: dict[str, Any]) -> EntitySchema:
        """Create an entity and record lineage for the change."""
        created = await self.entities.create(payload)
        self._lineage.record(
            entity_id=created.id,
            action="created",
            before=None,
            after=created.model_dump(mode="json"),
        )
        return created

    async def get_entity(self, entity_id: str) -> EntitySchema:
        """Fetch a single entity by id."""
        return await self.entities.get(entity_id)

    async def update_entity(
        self, entity_id: str, changes: dict[str, Any], *, actor: str | None = None
    ) -> EntitySchema:
        """Apply a partial update and record the before/after in lineage."""
        before = (await self.entities.get(entity_id)).model_dump(mode="json")
        updated = await self.entities.update(entity_id, changes)
        self._lineage.record(
            entity_id=entity_id,
            action="updated",
            before=before,
            after=updated.model_dump(mode="json"),
            actor=actor,
        )
        return updated

    async def delete_entity(self, entity_id: str, *, actor: str | None = None) -> None:
        """Delete an entity and record an ``deleted`` lineage event."""
        before = (await self.entities.get(entity_id)).model_dump(mode="json")
        await self.entities.delete(entity_id)
        self._lineage.record(
            entity_id=entity_id,
            action="deleted",
            before=before,
            after=None,
            actor=actor,
        )

    async def list_entities(
        self,
        *,
        entity_type: str | None = None,
        active_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EntitySchema]:
        """Delegate to :meth:`EntityService.list_entities`."""
        return await self.entities.list_entities(
            entity_type=entity_type, active_at=active_at, limit=limit, offset=offset
        )

    # =========================================================================
    # RELATIONSHIP CRUD (temporal)
    # =========================================================================

    async def create_relationship(
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
        """Create a temporal relationship between two existing entities."""
        return await self.relationships.create(
            source_id,
            target_id,
            relation_type,
            properties=properties,
            valid_from=valid_from,
            valid_to=valid_to,
            asserted_at=asserted_at,
            confidence=confidence,
            evidence=evidence,
        )

    async def get_relationship(self, rel_id: str) -> RelationshipSchema:
        """Fetch a single relationship by id."""
        return await self.relationships.get(rel_id)

    async def close_relationship(
        self, rel_id: str, at: datetime | None = None
    ) -> RelationshipSchema:
        """Close the validity window of a relationship (idempotent)."""
        return await self.relationships.close(rel_id, at)

    async def relationships_active_at(
        self,
        entity_id: str,
        at: datetime | None = None,
        *,
        direction: str = "outgoing",
    ) -> list[RelationshipSchema]:
        """Relationships touching ``entity_id`` that are active at ``at``."""
        return await self.relationships.active_at(entity_id, at, direction=direction)

    async def active_snapshot(self, at: datetime | None = None) -> list[RelationshipSchema]:
        """Every relationship active at ``at`` (default: now)."""
        return await self.relationships.active_snapshot(at)

    # =========================================================================
    # ENTITY RESOLUTION
    # =========================================================================

    async def resolve_entity(
        self,
        entity: EntitySchema,
        *,
        threshold: float = 0.7,
        actor: str | None = None,
        auto_merge: bool = True,
    ) -> list[MergeResult]:
        """Find duplicate candidates for ``entity`` and (optionally) merge them."""
        return await self.resolver.resolve(
            entity, threshold=threshold, actor=actor, auto_merge=auto_merge
        )

    async def merge_entities(
        self,
        canonical_id: str,
        absorbed_ids: list[str],
        *,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> MergeResult:
        """Merge ``absorbed_ids`` into ``canonical_id`` (canonical survives)."""
        return await self.resolver.merge(
            canonical_id, absorbed_ids, actor=actor, details=details
        )

    async def find_duplicate_candidates(
        self,
        entity: EntitySchema,
        *,
        threshold: float = 0.7,
    ) -> list[MatchCandidate]:
        """Return scored duplicate candidates for ``entity``."""
        return await self.resolver.find_candidates(entity, threshold=threshold)

    # =========================================================================
    # TIME TRAVEL + LINEAGE
    # =========================================================================

    async def state_at(self, at: datetime | None = None) -> GraphState:
        """Reconstruct the full graph state at ``at`` (default: now)."""
        return await self.time_travel.state_at(at)

    async def entity_at(self, entity_id: str, at: datetime | None = None) -> EntitySchema | None:
        """The entity as it stood at ``at``, or ``None``."""
        return await self.time_travel.entity_at(entity_id, at)

    async def diff(self, before: datetime | None = None, after: datetime | None = None) -> StateDiff:
        """Difference between graph state at ``before`` and at ``after``."""
        return await self.time_travel.diff(before, after)

    def lineage_trace(self, entity_id: str) -> list[LineageEvent]:
        """Full recorded change history for an entity."""
        return self._lineage.trace(entity_id)

    def entity_lineage_state(
        self, entity_id: str, at: datetime
    ) -> dict[str, Any] | None:
        """Reconstruct an entity's state as of an instant from lineage events."""
        return self._lineage.entity_at(entity_id, at)

    # =========================================================================
    # DERIVATION
    # =========================================================================

    async def derive_relationships(
        self, *, at: datetime | None = None, limit: int = 10_000
    ) -> list[DerivationResult]:
        """Run all derivation rules against the active graph at ``at``."""
        return await self.derivation.run(at=at, limit=limit)
