"""Entity records (NerveCenter spec Section 12).

Entities are nodes in the NerveCenter knowledge graph. Every entity is
evidence-backed: it records *where* its facts came from via ``source_evidence``
and carries a temporal validity window expressing *when* the entity's facts hold.

Assumptions (spec Section 12 not present in the repository):
    - ``entity_type`` is a closed-ish classification literal that matches the
      kinds of things a personal-intelligence core tracks (people, places,
      documents, artifacts, concepts, devices, agents, ...).
    - ``confidence`` (0..1) reflects how certain the core is of the entity.
    - ``valid`` is a :class:`TemporalWindow` scoping when the entity's facts apply.
"""

from typing import Any, Literal

from pydantic import Field

from .base import Record, TemporalWindow

#: Classification of a knowledge-graph node.
EntityType = Literal[
    "person",
    "organization",
    "place",
    "document",
    "artifact",
    "concept",
    "device",
    "agent",
    "credential",
    "resource",
    "other",
]


class Entity(Record):
    """A node in the NerveCenter knowledge graph."""

    entity_type: EntityType = Field(
        ...,
        description="Classification of the entity.",
    )
    name: str = Field(
        ...,
        description="Primary human-readable name of the entity.",
    )
    description: str | None = Field(
        default=None,
        description="Free-form summary of the entity.",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, type-specific key/value attributes.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names and identifiers the entity is known by.",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence (0..1) that this entity and its attributes are correct.",
    )
    valid: TemporalWindow = Field(
        default_factory=TemporalWindow,
        description="Time interval during which the entity's facts hold.",
    )
    source_evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records backing this entity.",
    )
