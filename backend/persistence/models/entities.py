"""Entity ORM model mapping :class:`~schemas.entities.Entity`.

The ``entities`` table stores knowledge-graph nodes with their type, name,
description, and optional temporal validity window. Every entity is evidence-backed
(see Section 12 of the specification).

Table columns
-------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``entity_type`` (text) — classification (person|organization|place|document|...).
- ``name`` (text) — primary human-readable name.
- ``description`` (text, nullable) — free-form summary.
- ``attributes`` (JSONB) — type-specific key/value pairs.
- ``aliases`` (JSONB array of text) — alternative names.
- ``confidence`` (float) — certainty (0..1).
- ``valid_from`` / ``valid_to`` (timestamptz, nullable) — temporal validity window.
- ``source_evidence`` (JSONB array of UUID text) — evidence citations.

Indexes
-------
- ``ix_entities_entity_type`` — type-filtered queries.
- ``ix_entities_name`` — name lookup.
- ``ix_entities_valid_window`` — temporal validity queries (btree with GIN fallback).
- ``ix_entities_source_evidence`` — evidence-backed reverse lookup (GIN).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Entity(Base):
    """ORM mapping of :class:`~schemas.entities.Entity`."""

    __tablename__ = "entities"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    aliases: Mapped[list[str]] = mapped_column(Jsonb, default=list)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(
        "valid_from", DateTime(timezone=True), nullable=True
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        "valid_to", DateTime(timezone=True), nullable=True
    )
    source_evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )

    __table_args__ = (
        Index(
            "ix_entities_entity_type_name",
            "entity_type",
            "name",
        ),
        Index(
            "ix_entities_valid_window",
            "valid_from",
            "valid_to",
        ),
        Index(
            "ix_entities_source_evidence_gin",
            "source_evidence",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Entity id={self.id!r} type={self.entity_type!r} "
            f"name={self.name!r}>"
        )
