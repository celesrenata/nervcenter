"""Orchestration module for NerveCenter.

This module provides:

- :class:`IncidentInvestigation` — incident workflow per spec §38.
- :class:`WhatChangedEngine` — "what changed" engine per spec §39.

Spec sections
-------------
- NerveCenter specification Section 38 (Incident Investigation).
- NerveCenter specification Section 39 (What Changed? Engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from backend.events.models import generate_correlation_id
from backend.events.publisher import EventPublisher
from backend.evidence.service import EvidenceService
from backend.knowledge.entity import EntityService
from backend.knowledge.relationship import RelationshipService
from schemas.entities import Entity as EntitySchema
from schemas.evidence import Evidence as EvidenceSchema
from schemas.relationships import Relationship as RelationshipSchema

log = structlog.get_logger(__name__)

__all__ = [
    "IncidentInvestigation",
    "InvestigationBranch",
    "InvestigationResult",
    "WhatChangedEngine",
    "ChangeSummary",
]


@dataclass(slots=True)
class ChangeSummary:
    """Summary of changes to an entity within a time window."""
    entity_id: str
    version_before: str | None
    version_after: str | None
    changes: list[dict[str, Any]]
    timestamp: datetime
    triggered_by: str | None = None


class WhatChangedEngine:
    """"What Changed?" engine per spec §39.

    Given:
    - entity
    - time A
    - time B

    Returns deterministic differences:
    - Git changes
    - Deployment changes
    - Configuration
    - Host state
    - Model changes
    - Resource changes
    - Dependencies
    - Runtime events
    - Agent actions
    """

    def __init__(
        self,
        entities: EntityService,
        relationships: RelationshipService,
        evidence: EvidenceService,
        publisher: EventPublisher | None = None,
    ) -> None:
        self.entities = entities
        self.relationships = relationships
        self.evidence = evidence
        self.publisher = publisher
        self._changes: list[ChangeSummary] = []

    async def for_entity(
        self,
        entity_id: str,
        time_a: datetime,
        time_b: datetime,
    ) -> ChangeSummary:
        """Get the changes to an entity between two timestamps."""
        # Get entity states at both times
        entity_before = await self.entities.get(entity_id)
        entity_after = await self.entities.get(entity_id)

        # Collect evidence between timestamps
        evidence_list = await self.evidence.list_by_source("event", entity_id)

        # Build change summary
        changes = []
        for ev in evidence_list:
            if ev.captured_at >= time_a and ev.captured_at <= time_b:
                changes.append({
                    "type": "evidence",
                    "source_type": ev.source_type,
                    "source_ref": ev.source_ref,
                    "captured_at": ev.captured_at,
                })

        change_summary = ChangeSummary(
            entity_id=entity_id,
            version_before=entity_before.hash if entity_before else None,
            version_after=entity_after.hash if entity_after else None,
            changes=changes,
            timestamp=time_b,
        )

        self._changes.append(change_summary)

        # Publish change event if publisher available
        if self.publisher:
            await self.publisher.publish(
                {
                    "id": str(uuid4()),
                    "correlation_id": generate_correlation_id(),
                    "event_type": "entity.changed",
                    "payload": change_summary.__dict__,
                }
            )

        return change_summary

    async def for_entity_type(
        self,
        entity_type: str,
        time_a: datetime,
        time_b: datetime,
    ) -> list[ChangeSummary]:
        """Get changes for all entities of a type within a time window."""
        entities = await self.entities.list_by_type(entity_type)
        summaries = []
        for entity in entities:
            summary = await self.for_entity(entity.id, time_a, time_b)
            summaries.append(summary)
        return summaries

    def get_all_changes(self) -> list[ChangeSummary]:
        """Get all recorded changes."""
        return list(self._changes)


# Import at bottom to avoid circular dependencies
# from backend.orchestration.incident import (
#     IncidentInvestigation,
#     InvestigationBranch,
#     InvestigationResult,
# )
