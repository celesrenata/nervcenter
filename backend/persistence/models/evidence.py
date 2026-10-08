"""Evidence ORM model mapping :class:`~schemas.evidence.Evidence`.

The ``evidence`` table stores provenance records that every claim and entity cites.
Every evidence record points to *where* a fact came from (URL, file, transcript, …)
and how trustworthy that source is (see Section 15 of the specification).

Table columns
-------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``source_type`` (text) — classification (web_page|document|transcript|...).
- ``source_ref`` (text) — locating reference (URL, path, URI, or id).
- ``content`` (text, nullable) — captured text or excerpt (may be redacted).
- ``content_hash`` (SHA-256, nullable) — digest of the captured content.
- ``captured_at`` (timestamp) — when the content was captured.
- ``trust`` (float) — source trust score (0..1).
- ``metadata`` (JSONB) — capture-time metadata (http status, tool name, ...).
- ``redacted`` (boolean) — whether content was redacted by policy.

Indexes
-------
- ``ix_evidence_source_type`` — source-type filtering.
- ``ix_evidence_source_ref`` — source reference lookup.
- ``ix_evidence_content_hash`` — content-integrity verification.
- ``ix_evidence_captured_at`` — temporal queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Evidence(Base):
    """ORM mapping of :class:`~schemas.evidence.Evidence`.

    ``metadata`` shadows :class:`DeclarativeBase.metadata` on the class; the
    resulting ``SAWarning`` is pre-existing and intentional (column name
    matches the spec/contract field ``metadata``).
    """

    __tablename__ = "evidence"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime]
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # NOTE: captured_at must be a real timestamp column (matches the alembic
    # 001 DDL ``sa.DateTime(timezone=True)``). An earlier draft declared it as
    # ``String`` while the annotation said ``datetime``, which broke inserts on
    # any dialect that enforces type fidelity.
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    trust: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    # Pre-existing SAWarning: the ``metadata`` column shadows
    # ``DeclarativeBase.metadata``. Kept because the v0 contract field is
    # named ``metadata`` and renaming would break the schemas contract.
    metadata: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)
    redacted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index(
            "ix_evidence_source_type_captured_at",
            "source_type",
            "captured_at",
        ),
        Index(
            "ix_evidence_source_ref_hash",
            "source_ref",
            "content_hash",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Evidence id={self.id!r} source_type={self.source_type!r} "
            f"source_ref={self.source_ref!r}>"
        )
