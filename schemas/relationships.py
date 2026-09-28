"""Relationship records (NerveCenter spec Section 13).

Relationships are directed edges between :class:`~schemas.entities.Entity` nodes
in the knowledge graph. Each relationship carries a **temporal validity window**
expressing *when* the relation is or was true, in addition to ``asserted_at``
(the moment the core recorded it).

Assumptions (spec Section 13 not present in the repository):
    - ``relation_type`` is a classification literal covering the most common
      personal-intelligence relations, with ``other`` as an escape hatch.
    - Relationships are evidence-backed and carry a ``confidence``.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from .base import Record, TemporalWindow

#: Classification of a directed knowledge-graph edge.
RelationType = Literal[
    "member_of",
    "parent_of",
    "child_of",
    "owns",
    "owned_by",
    "located_in",
    "part_of",
    "depends_on",
    "created_by",
    "created",
    "supports",
    "contradicts",
    "related_to",
    "other",
]


class Relationship(Record):
    """A directed, time-scoped edge between two entities."""

    source_entity_id: str = Field(
        ...,
        description="Id of the source entity of this relationship.",
    )
    target_entity_id: str = Field(
        ...,
        description="Id of the target entity of this relationship.",
    )
    relation_type: RelationType = Field(
        ...,
        description="Classification of the relationship.",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed, relation-specific properties.",
    )
    valid: TemporalWindow = Field(
        default_factory=TemporalWindow,
        description="Temporal validity window: when this relationship is / was true.",
    )
    asserted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the core first asserted this relationship (UTC).",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence (0..1) in the truth of this relationship.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records supporting this relationship.",
    )
