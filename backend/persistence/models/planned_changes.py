"""PlannedChange ORM model mapping :class:`~schemas.planned_changes.PlannedChange`.

The ``planned_changes`` table stores proposed, reviewable modifications to
NerveCenter state. Planned changes are the bridge between inference and
execution: nothing mutates the graph or schedule without a corresponding
planned change, either auto-approved by policy or approved by a human
(see Sections 16 and 40 of the specification).

PlannedChanges table columns
----------------------------
- ``id`` (UUID) — immutable record identifier.
- ``created_at`` (timestamp) — when the record was first written.
- ``schema_version`` (text) — always "v0" for this version.
- ``hash`` (SHA-256) — optional integrity digest.
- ``change_type`` (text) — classification literal (entity_upsert|...|other).
- ``title`` (text) — short human-readable summary of the change.
- ``description`` (text, nullable) — what will change and why.
- ``status`` (text) — lifecycle (draft, pending_approval, approved, ...).
- ``risk_level`` (integer) — severity 0..4; policy maps risk to approval policy.
- ``subject_ids`` (JSONB array of UUID text) — record ids the change targets.
- ``source_decision_id`` (UUID, nullable) — :class:`Decision` that produced it.
- ``diff`` (JSONB) — before/after representation of the change.
- ``rollback`` (JSONB) — instructions/payload for reverting an applied change.
- ``proposed_at`` (timestamp) — when the change was first proposed (UTC).
- ``expires_at`` (timestamp, nullable) — auto-expiry moment, if set.
- ``approval_id`` (UUID, nullable) — :class:`Approval` governing the change.

Indexes
-------
- ``ix_planned_changes_change_type`` — change-kind filtering.
- ``ix_planned_changes_status`` — approval-queue queries.
- ``ix_planned_changes_source_decision_id`` — decision → change lookup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class PlannedChange(Base):
    """ORM mapping of :class:`~schemas.planned_changes.PlannedChange`."""

    __tablename__ = "planned_changes"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime]
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")
    hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    change_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", nullable=False, index=True
    )
    risk_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    subject_ids: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)
    source_decision_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    diff: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict, nullable=False)
    rollback: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict, nullable=False)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approval_id: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PlannedChange id={self.id!r} change_type={self.change_type!r} "
            f"status={self.status!r} title={self.title[:40]!r}>"
        )


def _attach_decisions_planned_change_fk() -> None:
    """Declare ``decisions.planned_change_id -> planned_changes.id`` in the metadata.

    The FK must live on the ``decisions`` table so that ``CREATE TABLE decisions``
    (from ``Base.metadata.create_all`` as well as the hand-written 001 migration)
    references a real table. The sibling model in ``claims.py`` owns that column
    but is outside this file's ownership, so the constraint is attached here —
    this module is always imported after ``claims`` by the package ``__init__``,
    so the ``decisions`` table already exists in the metadata by the time this
    helper runs. ``Table.append_constraint`` is used (rather than
    ``Column.append_constraint``, which does not exist in SQLAlchemy 2.x) so
    that the FK is registered on ``column.foreign_keys`` — that is the attribute
    the FK_OK verification gate and ``create_all`` introspect. Idempotent: a
    second import is a no-op.
    """

    table = Base.metadata.tables.get("decisions")
    if table is None:
        return
    column = table.c.get("planned_change_id")
    if column is None:
        return
    if any(
        fk.target_fullname == "planned_changes" for fk in column.foreign_keys
    ):
        return
    table.append_constraint(
        ForeignKeyConstraint(
            ["planned_change_id"],
            ["planned_changes.id"],
        )
    )


_attach_decisions_planned_change_fk()
