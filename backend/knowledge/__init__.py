"""Knowledge plane: entities, temporal relationships, and graph queries.

This package maintains the *current state* of the knowledge graph, the
*temporal relationships* between entities (each fact is true over a validity
window), and *entity resolution* (deduplicating / canonicalizing entities).

Subsystems
----------
- :mod:`~backend.knowledge.entity` — :class:`EntityService` (entity CRUD).
- :mod:`~backend.knowledge.relationship` — :class:`RelationshipService`
  (temporal relationship management and windowed queries).
- :mod:`~backend.knowledge.resolution` — :class:`EntityResolver`
  (merging duplicates, canonical names/aliases).
- :mod:`~backend.knowledge.history` — :class:`TimeTravelQuery` and
  :class:`LineageTracker` (historical state reconstruction + lineage).
- :mod:`~backend.knowledge.derivation` — :class:`DerivationEngine`
  (implied relationships from asserted ones).
- :mod:`~backend.knowledge.service` — :class:`KnowledgeService`, the single
  high-level facade wiring all of the above together.

Typical wiring::

    from backend.persistence import create_persistence, config_from_env
    from backend.knowledge import KnowledgeService

    engine, session_factory = create_persistence(config_from_env())
    knowledge = KnowledgeService(engine, session_factory)

    entity = await knowledge.create_entity(
        {"entity_type": "person", "name": "Ada Lovelace"}
    )
    other = await knowledge.create_relationship(
        entity.id, "abc...", "created", valid_from=..., valid_to=...
    )
    await knowledge.derive_relationships()
    state = await knowledge.state_at()

Spec sections
-------------
- NerveCenter specification Section 12 (Entity Model).
- NerveCenter specification Section 13 (Temporal Relationships).
"""

from .derivation import (
    DEFAULT_RULES,
    DerivedRelationship,
    DerivationEngine,
    DerivationResult,
    DerivationRule,
)
from .entity import (
    EntityConflictError,
    EntityNotFoundError,
    EntityService,
)
from .history import (
    GraphState,
    LineageEvent,
    LineageTracker,
    StateDiff,
    TimeTravelQuery,
)
from .relationship import UnknownEntityError, RelationshipService
from .resolution import EntityResolver, MatchCandidate, MergeResult
from .service import KnowledgeService

__all__ = [
    # service facade
    "KnowledgeService",
    # entity
    "EntityService",
    "EntityNotFoundError",
    "EntityConflictError",
    # relationship
    "RelationshipService",
    "UnknownEntityError",
    # resolution
    "EntityResolver",
    "MatchCandidate",
    "MergeResult",
    # history
    "TimeTravelQuery",
    "LineageTracker",
    "LineageEvent",
    "GraphState",
    "StateDiff",
    # derivation
    "DerivationEngine",
    "DerivationRule",
    "DerivedRelationship",
    "DerivationResult",
    "DEFAULT_RULES",
]
