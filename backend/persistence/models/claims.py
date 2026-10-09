"""Claim and Decision ORM models mapping :class:`~schemas.claims.Claim` and :class:`~schemas.claims.Decision`.

The ``claims`` table stores propositions formed from evidence, with a lifecycle
(state machine) and confidence. The ``decisions`` table stores actions the system
took based on those claims (see Sections 16 and 10/15 of the specification).

Claims table columns
--------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``statement`` (text) — the claim, stated as a single sentence.
- ``subject_entity_id`` (UUID, nullable) — primary entity the claim is about.
- ``status`` (text) — lifecycle (open|supported|contradicted|superseded|rejected).
- ``confidence`` (float) — certainty (0..1).
- ``supporting_evidence`` / ``contradicting_evidence`` (JSONB arrays) — citations.
- ``derived_from_claims`` (JSONB array of UUID text) — inference lineage.
- ``supersedes_claim_id`` (UUID, nullable) — replacement chain.
- ``attributes`` (JSONB) — structured data (values, ranges, tags, ...).

Decisions table columns
-----------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``claim_id`` (UUID) — the claim this decision acted on.
- ``statement`` (text) — restatement of the decision taken.
- ``mechanism`` (text) — how reached (heuristic|model_inference|human|policy|orchestrator).
- ``rationale`` (text, nullable) — explainable rationale.
- ``action`` (text) — machine-readable action identifier.
- ``supporting_evidence`` (JSONB array) — justifying evidence.
- ``planned_change_id`` (UUID, nullable) — resulting change id.
- ``task_id`` (UUID, nullable) — resulting task id.
- ``decided_at`` (timestamp) — when the decision was made.

Indexes
-------
- ``ix_claims_status`` — state-machine queries.
- ``ix_claims_status_subject`` — status-filtered entity queries.
- ``ix_decisions_claim_id`` — decision history for a claim.
- ``ix_decisions_action`` — action-type queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class Claim(Base):
    """ORM mapping of :class:`~schemas.claims.Claim`."""

    __tablename__ = "claims"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    statement: Mapped[str] = mapped_column(String, nullable=False)
    subject_entity_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(default=0.5, nullable=False)
    supporting_evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    contradicting_evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    derived_from_claims: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    supersedes_claim_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict)

    __table_args__ = (
        Index(
            "ix_claims_status_subject",
            "status",
            "subject_entity_id",
        ),
        Index(
            "ix_claims_status_created_at",
            "status",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<Claim id={self.id!r} status={self.status!r} statement={self.statement[:40]!r}...>"


class Decision(Base):
    """ORM mapping of :class:`~schemas.claims.Decision`."""

    __tablename__ = "decisions"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    claim_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(String, nullable=False)
    mechanism: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String(255), default="no_action", nullable=False)
    supporting_evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )
    planned_change_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_decisions_claim_id_mechanism",
            "claim_id",
            "mechanism",
        ),
        Index(
            "ix_decisions_action_created_at",
            "action",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<Decision id={self.id!r} claim_id={self.claim_id!r} action={self.action!r}>"
