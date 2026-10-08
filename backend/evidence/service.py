"""Evidence service for NerveCenter.

This module implements :class:`EvidenceService`, the async CRUD + lifecycle
layer for the ``evidence`` table (NerveCenter specification Section 15).
It mirrors the design of :class:`~backend.knowledge.entity.EntityService`
and :class:`~backend.goals.service.GoalService`:

- Every mutating method runs inside a single transaction (commit on success,
  rollback on error).
- Records are returned as :class:`~schemas.evidence.Evidence` (pydantic) so
  callers never see ORM rows.
- Temporal columns are normalized on the ORM boundary.

Section 15 semantics implemented here
--------------------------------------
- **capture**: :meth:`create` stores the captured ``content`` together with
  its SHA-256 digest (``content_hash``) and the capture timestamp
  (``captured_at``).  Redacted captures keep ``content = NULL`` and carry the
  ``redacted`` flag; reference-only captures may carry a pre-computed
  ``content_hash`` with no stored content.
- **provenance**: :meth:`get` returns the full record (source, capture time,
  trust, metadata, integrity digests) for a stable evidence id.
- **citation index**: :meth:`list_by_source` returns every record citing a
  given (``source_type``, ``source_ref``) pair, newest capture first.
- **integrity**: :meth:`verify_content` recomputes the SHA-256 digest of the
  stored content and compares it against the stored ``content_hash`` and the
  caller's ``expected_hash``.

Spec sections
-------------
- NerveCenter specification Section 15 (Evidence System).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from backend.persistence.models import Evidence as EvidenceORM
from schemas.evidence import Evidence as EvidenceSchema

log = structlog.get_logger(__name__)

__all__ = ["EvidenceService"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    """SHA-256 hex digest of the captured content (UTF-8 encoded)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_datetime(value: Any) -> datetime | None:
    """Coerce an ORM temporal value (datetime or ISO string) to an aware UTC datetime.

    Naive values (as returned by non-Postgres test dialects) are assumed to be
    UTC, mirroring the knowledge/goals plane boundary normalization.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def _orm_to_schema(orm: EvidenceORM) -> EvidenceSchema:
    """Project an ORM evidence row onto the v0 pydantic schema."""
    created_at = _as_datetime(orm.created_at)
    captured_at = _as_datetime(orm.captured_at)
    return EvidenceSchema(
        id=str(orm.id),
        created_at=created_at if created_at is not None else datetime.now(UTC),
        schema_version=orm.schema_version or "v0",
        hash=orm.hash,
        source_type=orm.source_type,
        source_ref=orm.source_ref,
        content=orm.content,
        content_hash=orm.content_hash,
        captured_at=captured_at if captured_at is not None else datetime.now(UTC),
        trust=float(orm.trust or 0.0),
        metadata=dict(orm.metadata or {}),
        redacted=bool(orm.redacted),
    )


class EvidenceService:
    """Async service for evidence records (capture, provenance, citation)."""

    def __init__(self, engine: AsyncEngine):
        """Initialize with a SQLAlchemy async engine."""
        self._engine = engine
        self._sessionmaker = async_sessionmaker(
            bind=engine, expire_on_commit=False
        )

    # ------------------------------------------------------------------
    # capture
    # ------------------------------------------------------------------

    async def create(
        self,
        source_type: str,
        source_ref: str,
        content: str | None = None,
        captured_at: datetime | None = None,
        trust: float = 0.5,
        metadata: dict[str, Any] | None = None,
        redacted: bool = False,
        content_hash: str | None = None,
    ) -> EvidenceSchema:
        """Capture a new evidence record and persist it.

        Capture semantics (spec Section 15):

        - ``content`` is stored verbatim (or ``NULL`` for redacted /
          reference-only captures) and its SHA-256 digest is stored as
          ``content_hash`` so the citation stays verifiable even if the
          original artifact moves or disappears.
        - An explicit ``content_hash`` is honoured when no content is
          captured (reference-only provenance).
        - ``captured_at`` defaults to now (UTC).
        - The record's integrity ``hash`` (``Record.fingerprint``) is set at
          capture time; the evidence record is immutable afterwards.

        Raises:
            pydantic.ValidationError: when the payload fails v0 schema
                validation (invalid ``source_type`` literal or ``trust``
                outside 0..1).
        """
        now = datetime.now(UTC)
        captured = captured_at if captured_at is not None else now
        digest = content_hash
        if content is not None and digest is None:
            digest = _sha256(content)

        # Validate against the v0 contract before touching the database.
        record = EvidenceSchema(
            id=str(uuid4()),
            created_at=now,
            source_type=source_type,
            source_ref=source_ref,
            content=content,
            content_hash=digest,
            captured_at=captured,
            trust=trust,
            metadata=dict(metadata or {}),
            redacted=redacted,
        )
        record.hash = record.fingerprint()

        orm = EvidenceORM(
            id=record.id,
            created_at=record.created_at,
            schema_version=record.schema_version,
            hash=record.hash,
            source_type=record.source_type,
            source_ref=record.source_ref,
            content=record.content,
            content_hash=record.content_hash,
            captured_at=record.captured_at,
            trust=record.trust,
            metadata=record.metadata,
            redacted=record.redacted,
        )

        async with self._sessionmaker() as session:
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            out = _orm_to_schema(orm)

        log.info(
            "evidence.created",
            evidence_id=out.id,
            source_type=out.source_type,
            source_ref=out.source_ref,
            content_hash=out.content_hash,
            redacted=out.redacted,
        )
        return out

    # ------------------------------------------------------------------
    # provenance
    # ------------------------------------------------------------------

    async def get(self, evidence_id: str) -> EvidenceSchema | None:
        """Look up a single evidence record by its stable id.

        Returns:
            The full provenance record, or ``None`` when the id is unknown
            or not a valid UUID.
        """
        async with self._sessionmaker() as session:
            try:
                orm = await session.get(EvidenceORM, evidence_id)
            except (ValueError, TypeError):
                # Malformed id (e.g. not a UUID): treat as unknown.
                return None
            if orm is None:
                return None
            return _orm_to_schema(orm)

    # ------------------------------------------------------------------
    # citation index
    # ------------------------------------------------------------------

    async def list_by_source(
        self, source_type: str, source_ref: str
    ) -> list[EvidenceSchema]:
        """Return the citation index for a source.

        Every evidence record citing ``(source_type, source_ref)`` is
        returned, newest capture first, so citations stay chronological
        while the record itself remains immutable.
        """
        stmt = (
            select(EvidenceORM)
            .where(EvidenceORM.source_type == source_type)
            .where(EvidenceORM.source_ref == source_ref)
            .order_by(EvidenceORM.captured_at.desc(), EvidenceORM.created_at.desc())
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [_orm_to_schema(row) for row in rows]

    async def list_evidence(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[EvidenceSchema]:
        """List evidence records, newest capture first (API listing)."""
        stmt = (
            select(EvidenceORM)
            .order_by(EvidenceORM.captured_at.desc(), EvidenceORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [_orm_to_schema(row) for row in rows]

    # ------------------------------------------------------------------
    # lifecycle / integrity
    # ------------------------------------------------------------------

    async def delete(self, evidence_id: str) -> bool:
        """Delete an evidence record.

        Returns:
            ``True`` when a record was deleted, ``False`` when the id was
            unknown (or malformed).
        """
        async with self._sessionmaker() as session:
            try:
                orm = await session.get(EvidenceORM, evidence_id)
            except (ValueError, TypeError):
                return False
            if orm is None:
                return False
            await session.delete(orm)
            await session.commit()
        log.info("evidence.deleted", evidence_id=evidence_id)
        return True

    async def verify_content(self, evidence_id: str, expected_hash: str) -> bool:
        """Verify evidence integrity by recomputing the content digest.

        Recomputes the SHA-256 digest of the stored ``content`` and compares
        it against the stored ``content_hash`` and the caller's
        ``expected_hash``; both must match for verification to succeed.
        For redacted / reference-only captures (no stored content), only the
        stored digest can be checked against ``expected_hash``.

        Returns:
            ``False`` when the record is missing, when no digest is stored,
            or when any comparison fails.
        """
        async with self._sessionmaker() as session:
            try:
                orm = await session.get(EvidenceORM, evidence_id)
            except (ValueError, TypeError):
                return False
            if orm is None:
                return False

            stored = (orm.content_hash or "").lower() or None
            expected = (expected_hash or "").lower() or None

            if orm.content is not None:
                recomputed = _sha256(orm.content)
                return (
                    stored is not None
                    and recomputed == stored
                    and recomputed == expected
                )

            # Reference-only capture: integrity can only be asserted via
            # the stored digest.
            return stored is not None and stored == expected


