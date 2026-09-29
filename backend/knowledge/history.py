"""Time-travel queries and entity lineage for the knowledge plane.

This module provides two complementary facilities:

- :class:`TimeTravelQuery` — reconstruct the state of the knowledge graph at
  any instant in time: the entities and relationships whose temporal windows
  cover that instant, plus state diffs between two instants.
- :class:`LineageTracker` — an in-memory per-entity change log
  (before/after JSON snapshots plus actor/action metadata) that records what
  :class:`backend.knowledge.service.KnowledgeService` mutates, so the prior
  state of any entity can be reconstructed ("what did this entity look
  like at time T?").

Spec sections
-------------
- NerveCenter specification Section 12 (Entity Model) — validity windows.
- NerveCenter specification Section 13 (Temporal Relationships).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from schemas.base import TemporalWindow
from schemas.entities import Entity as EntitySchema
from schemas.relationships import Relationship as RelationshipSchema

from .entity import EntityNotFoundError, EntityService
from .relationship import RelationshipService


def _covers(window: TemporalWindow, at: datetime) -> bool:
    """Whether a half-open window (``[valid_from, valid_to)``) covers ``at``."""
    if window.valid_from is not None and window.valid_from > at:
        return False
    if window.valid_to is not None and window.valid_to <= at:
        return False
    return True


def snapshot(entity: EntitySchema) -> dict[str, Any]:
    """JSON-serializable snapshot of an entity (used as lineage state)."""
    return entity.model_dump(mode="json")


@dataclass(frozen=True)
class GraphState:
    """The state of the knowledge graph at one instant in time."""

    at: datetime
    entities: list[EntitySchema]
    relationships: list[RelationshipSchema]


@dataclass(frozen=True)
class StateDiff:
    """Difference between two :class:`GraphState` snapshots."""

    from_state: GraphState
    to_state: GraphState
    entities_added: list[EntitySchema]
    entities_removed: list[EntitySchema]
    relationships_added: list[RelationshipSchema]
    relationships_removed: list[RelationshipSchema]


class TimeTravelQuery:
    """Answers "what did the graph look like at time T"."""

    def __init__(self, entities: EntityService, relationships: RelationshipService) -> None:
        self._entities = entities
        self._relationships = relationships

    async def state_at(self, at: datetime | None = None) -> GraphState:
        """The full graph state at ``at`` (default: now).

        Includes every entity and relationship whose validity window covers
        ``at`` — i.e. the temporal relationship of the graph *at that time*.
        """
        when = at or datetime.now(UTC)
        ents = await self._entities.list_entities(active_at=when, limit=20_000)
        rels = await self._relationships.active_snapshot(when)
        return GraphState(at=when, entities=ents, relationships=rels)

    async def entity_at(
        self, entity_id: str, at: datetime | None = None
    ) -> EntitySchema | None:
        """The entity as it stood at ``at``, or ``None`` when absent/inactive."""
        when = at or datetime.now(UTC)
        try:
            entity = await self._entities.get(entity_id)
        except EntityNotFoundError:
            return None
        return entity if _covers(entity.valid, when) else None

    async def relationships_at(
        self,
        entity_id: str,
        at: datetime | None = None,
        *,
        direction: str = "both",
    ) -> list[RelationshipSchema]:
        """Relationships touching ``entity_id`` that are active at ``at``."""
        return await self._relationships.active_at(entity_id, at, direction=direction)

    async def diff(self, before: datetime | None = None, after: datetime | None = None) -> StateDiff:
        """Difference between the graph state at ``before`` and at ``after``."""
        start = await self.state_at(before)
        end = await self.state_at(after)
        start_entity_ids = {e.id for e in start.entities}
        end_entity_ids = {e.id for e in end.entities}
        start_rel_ids = {r.id for r in start.relationships}
        end_rel_ids = {r.id for r in end.relationships}
        return StateDiff(
            from_state=start,
            to_state=end,
            entities_added=[e for e in end.entities if e.id not in start_entity_ids],
            entities_removed=[e for e in start.entities if e.id not in end_entity_ids],
            relationships_added=[r for r in end.relationships if r.id not in start_rel_ids],
            relationships_removed=[r for r in start.relationships if r.id not in end_rel_ids],
        )


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

# Actions that make an entity "gone" in reconstruction.
_GONE_ACTIONS = frozenset({"deleted", "absorbed"})


@dataclass(frozen=True)
class LineageEvent:
    """One recorded change to an entity.

    ``before``/``after`` are JSON-serializable snapshots of the entity as it
    stood (``None`` when the entity did not exist). ``action`` is one of
    ``created``, ``updated``, ``deleted``, ``absorbed`` (entity resolution
    merge) or ``custom``.
    """

    event_id: str
    entity_id: str
    action: str
    at: datetime
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    actor: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class LineageTracker:
    """Per-entity change history (lineage) for the knowledge plane.

    The tracker is in-memory by design: it is a *view* over what
    :class:`backend.knowledge.service.KnowledgeService` records, not an
    authority on the current state. It supports:

    - :meth:`trace` — the full ordered change history of an entity.
    - :meth:`entity_at` — reconstruct the entity's state as of an instant.
    - :meth:`latest` — the most recent event for an entity.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[LineageEvent]] = {}

    def record(
        self,
        *,
        entity_id: str,
        action: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
        at: datetime | None = None,
    ) -> LineageEvent:
        """Append one lineage event for ``entity_id``."""
        event = LineageEvent(
            event_id=str(uuid4()),
            entity_id=entity_id,
            action=action,
            at=at or datetime.now(UTC),
            before=before,
            after=after,
            actor=actor,
            details=dict(details or {}),
        )
        self._events.setdefault(entity_id, []).append(event)
        return event

    def trace(self, entity_id: str) -> list[LineageEvent]:
        """All recorded events for ``entity_id``, in time order."""
        return list(self._events.get(entity_id, ()))

    def latest(self, entity_id: str) -> LineageEvent | None:
        """The most recently recorded event for ``entity_id`` (or ``None``)."""
        events = self._events.get(entity_id)
        return events[-1] if events else None

    def events(self) -> list[LineageEvent]:
        """Every recorded event across all entities, in time order."""
        all_events: list[LineageEvent] = []
        for events in self._events.values():
            all_events.extend(events)
        all_events.sort(key=lambda e: e.at)
        return all_events

    def entity_at(self, entity_id: str, at: datetime) -> dict[str, Any] | None:
        """Reconstruct the last recorded state of ``entity_id`` at/before ``at``.

        Replays the entity's events (in time order, ignoring those after
        ``at``) and returns the resulting JSON snapshot, or ``None`` when the
        entity had not been created yet or is deleted/absorbed as of ``at``.
        """
        current: dict[str, Any] | None = None
        for event in sorted(self._events.get(entity_id, ()), key=lambda e: e.at):
            if event.at > at:
                break
            if event.action in _GONE_ACTIONS:
                current = None
            elif event.after is not None:
                current = event.after
        return current

    def clear(self) -> None:
        """Drop all recorded events."""
        self._events.clear()
