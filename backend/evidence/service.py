"""Evidence service for NerveCenter.

This module implements :class:`EvidenceService`, the async CRUD + lifecycle layer
for the ``evidence`` table (NerveCenter specification Section 15). It mirrors
the design of :class:`~backend.knowledge.entity.EntityService`:

- Every mutating method runs inside a single transaction (commit on success,
  rollback on error).
- Records are returned as :class:`~schemas.evidence.Evidence` (pydantic) so callers
  never see ORM rows.
- Temporal columns are normalized to ISO-8601 strings at the ORM boundary,
  exactly as the knowledge plane does.

Spec sections
-------------
- NerveCenter specification Section 15 (Evidence System).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from schemas.evidence import Evidence as EvidenceSchema

log = structlog.get_logger(__name__)

__all__ = ["EvidenceService"]


class EvidenceService:
    """Async service for evidence records."""

    def __init__(self, engine: AsyncEngine):
        """Initialize with a SQLAlchemy async engine."""
        self._engine = engine
        self._sessionmaker = async_sessionmaker(
            bind=engine, expire_on_commit=False
        )

    async def create(
        self,
        source_type: str,
        source_ref: str,
        content: str | None = None,
        captured_at: datetime | None = None,
        trust: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceSchema:
        """Create a new evidence record."""
        raise NotImplementedError("EvidenceService.create() requires Evidence ORM model")

    async def get(self, evidence_id: str) -> EvidenceSchema | None:
        """Get an evidence record by ID."""
        raise NotImplementedError("EvidenceService.get() requires Evidence ORM model")

    async def list_by_source(
        self, source_type: str, source_ref: str
    ) -> list[EvidenceSchema]:
        """List evidence records for a specific source."""
        raise NotImplementedError("EvidenceService.list_by_source() requires Evidence ORM model")

    async def verify_content(self, evidence_id: str, expected_hash: str) -> bool:
        """Verify that evidence content matches the expected hash."""
        raise NotImplementedError("EvidenceService.verify_content() requires Evidence ORM model")
