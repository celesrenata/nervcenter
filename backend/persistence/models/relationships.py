"""Relationship ORM model mapping :class:`~schemas.relationships.Relationship`.

The ``relationships`` table stores directed edges between entities with a
temporal validity window. Every relationship is evidence-backed (see Section 13
of the specification).

Table columns
-------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``source_entity_id`` (UUID) — source entity.
- ``target_entity_id`` (UUID) — target entity.
- ``relation_type`` (text) — classification (member_of|parent_of|owns|...).
- ``properties`` (JSONB) — relation-specific typed properties.
- ``valid_from`` / ``valid_to`` (timestamptz, nullable) — temporal validity.
- ``asserted_at`` (timestamp) — when the core first asserted this relationship.
- ``confidence`` (float) — certainty (0..1).
- ``evidence`` (JSONB array of UUID text) — evidence citations.

Indexes
-------
- ``ix_relationships_source_target`` — bidirectional edge lookup.
- ``ix_relationships_relation_type`` — type-filtered queries.
- ``ix_relationships_source_entity_id`` / ``target_entity_id`` — node-centric
  neighborhood queries.
- ``ix_relationships_evidence_gin`` — evidence-backed reverse lookup (GIN).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Relationship(Base):
    """ORM mapping of :class:`~schemas.relationships.Relationship`."""

    __tablename__ = "relationships"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime]
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_entity_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    target_entity_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    valid_from: Mapped[datetime | None] = mapped_column(
        "valid_from", DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        "valid_to", DateTime(timezone=True), nullable=True
    )
    asserted_at: Mapped[datetime] = mapped_column(
        "asserted_at", DateTime(timezone=True), nullable=False
    )
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_relationships_source_target",
            "source_entity_id",
            "target_entity_id",
            "relation_type",
        ),
        Index(
            "ix_relationships_source_entity_id_valid",
            "source_entity_id",
            "valid_from",
            "valid_to",
        ),
        Index(
            "ix_relationships_target_entity_id_valid",
            "target_entity_id",
            "valid_from",
            "valid_to",
        ),
        Index(
            "ix_relationships_evidence_gin",
            "evidence",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Relationship id={self.id!r} "
            f"{self.source_entity_id!r}—{self.relation_type}→{self.target_entity_id!r}>"
        )
