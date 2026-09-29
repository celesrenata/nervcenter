"""Entity resolution: merge duplicate entities, canonicalize names/aliases.

NerveCenter's knowledge graph accumulates entities from multiple evidence
sources. When the same real-world object appears under different names (or
different sources create separate records for it), the graph carries
*duplicates* that should be consolidated. :class:`EntityResolver` performs
that consolidation:

- Finds candidate duplicates via name/alias/attribute matching.
- Merges two (or more) entities into one **canonical** entity, absorbing the
  others: their aliases, attributes, and evidence citations are unioned into
  the survivor; relationships pointing at absorbed entities are repointed to
  the canonical id.
- Tracks merges via the lineage system so a time-travel query can still
  surface the pre-merge state.

Spec sections
-------------
- NerveCenter specification Section 12 (Entity Model) — entity identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from schemas.entities import Entity as EntitySchema

from .entity import EntityService
from .history import LineageTracker, snapshot
from .relationship import RelationshipService

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchCandidate:
    """A single pair of entities that look like duplicates."""

    entity_a: EntitySchema
    entity_b: EntitySchema
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MergeResult:
    """Outcome of a merge operation."""

    canonical_id: str
    absorbed_ids: list[str]
    repointed_relationships: int
    merged_aliases: list[str]
    merged_evidence: list[str]
    at: datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EntityResolver:
    """Entity resolution: find duplicates and merge them.

    Uses the ``EntityService`` for CRUD and the ``RelationshipService`` to
    repoint edges. Lineage is recorded via an optional :class:`LineageTracker`
    so historical state can be reconstructed.
    """

    def __init__(
        self,
        entities: EntityService,
        relationships: RelationshipService,
        lineage: LineageTracker | None = None,
    ) -> None:
        self._entities = entities
        self._relationships = relationships
        self._lineage = lineage

    # -- candidate detection -------------------------------------------------

    async def find_candidates(
        self,
        entity: EntitySchema | None = None,
        *,
        name: str | None = None,
        entity_type: str | None = None,
        threshold: float = 0.7,
        limit: int = 50,
    ) -> list[MatchCandidate]:
        """Find entities that look like duplicates of ``entity`` or ``name``.

        Candidate pairs are scored on:
        - exact name match (score 1.0)
        - case-insensitive name match (score 0.9)
        - shared alias (score 0.8)
        - same entity_type (required filter, not a score factor)
        """
        target = entity
        if target is None and name is not None:
            # Build a lightweight search using find_by_name.
            results = await self._entities.find_by_name(name, entity_type)
            if not results:
                return []
            target = results[0]

        if target is None:
            raise ValueError("provide either entity or name")

        # Search by name (exact + case-insensitive) and by aliases.
        candidates: list[EntitySchema] = []

        # Exact name.
        by_name = await self._entities.find_by_name(target.name, entity_type or target.entity_type)
        candidates.extend(by_name)

        # Alias overlap.
        for alias in target.aliases:
            by_alias = await self._entities.find_by_alias(alias)
            candidates.extend(by_alias)

        # Score and filter.
        seen_ids = {target.id}
        scored: list[MatchCandidate] = []
        for cand in candidates:
            if cand.id in seen_ids:
                continue
            seen_ids.add(cand.id)
            score, reasons = self._score_pair(target, cand)
            if score >= threshold:
                scored.append(MatchCandidate(entity_a=target, entity_b=cand, score=score, reasons=reasons))

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:limit]

    def _score_pair(self, a: EntitySchema, b: EntitySchema) -> tuple[float, list[str]]:
        """Score how similar two entities are (0..1)."""
        score = 0.0
        reasons: list[str] = []

        # Same entity_type is a prerequisite (if different, score is 0).
        if a.entity_type != b.entity_type:
            return 0.0, ["different entity_type"]

        # Name comparison.
        if a.name.lower() == b.name.lower():
            if a.name == b.name:
                score = max(score, 1.0)
                reasons.append("exact name match")
            else:
                score = max(score, 0.9)
                reasons.append("case-insensitive name match")

        # Alias overlap.
        a_aliases = {x.lower() for x in a.aliases}
        b_aliases = {x.lower() for x in b.aliases}
        shared = a_aliases & b_aliases
        if shared:
            score = max(score, 0.8)
            reasons.append(f"shared aliases: {shared}")

        # Attribute overlap (bonus, capped).
        a_attrs = set(a.attributes.keys())
        b_attrs = set(b.attributes.keys())
        if a_attrs & b_attrs:
            overlap = len(a_attrs & b_attrs) / max(len(a_attrs | b_attrs), 1)
            score = min(1.0, score + 0.1 * overlap)
            reasons.append("attribute overlap")

        return score, reasons

    # -- merge ---------------------------------------------------------------

    async def merge(
        self,
        canonical_id: str,
        absorbed_ids: list[str],
        *,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> MergeResult:
        """Merge ``absorbed_ids`` into ``canonical_id``.

        Steps:
        1. Load canonical and all absorbed entities.
        2. Union aliases, attributes, and source_evidence into canonical.
        3. Re-point all relationships that reference absorbed ids to canonical.
        4. Delete absorbed entity rows.
        5. Record lineage for both canonical (updated) and each absorbed
           (absorbed).
        6. Return a :class:`MergeResult`.
        """
        if not absorbed_ids:
            raise ValueError("absorbed_ids must be non-empty")
        # Validate no self-merge.
        if canonical_id in absorbed_ids:
            raise ValueError("canonical_id cannot be in absorbed_ids")

        at = datetime.now(UTC)

        # Load all entities.
        all_ids = [canonical_id, *absorbed_ids]
        all_ents = await self._entities.batch_get(all_ids)
        found_ids = {e.id for e in all_ents}
        missing = [i for i in dict.fromkeys(all_ids) if i not in found_ids]
        if missing:
            raise ValueError(f"one or more entity ids do not exist: {missing}")

        canonical = next(e for e in all_ents if e.id == canonical_id)
        absorbed = {e.id: e for e in all_ents if e.id != canonical_id}

        # Union aliases.
        merged_aliases = set(canonical.aliases)
        for ent in absorbed.values():
            merged_aliases.update(ent.aliases)

        # Union attributes (canonical wins on conflict).
        merged_attrs = {**canonical.attributes}
        for ent in absorbed.values():
            for k, v in ent.attributes.items():
                if k not in merged_attrs:
                    merged_attrs[k] = v

        # Union evidence.
        merged_evidence = list(canonical.source_evidence)
        for ent in absorbed.values():
            for ev in ent.source_evidence:
                if ev not in merged_evidence:
                    merged_evidence.append(ev)

        # Update canonical.
        before_canonical = snapshot(canonical)
        await self._entities.update(
            canonical_id,
            {
                "aliases": list(merged_aliases),
                "attributes": merged_attrs,
                "source_evidence": merged_evidence,
            },
        )
        new_canonical = await self._entities.get(canonical_id)
        after_canonical = snapshot(new_canonical)

        # Record lineage for canonical.
        if self._lineage:
            self._lineage.record(
                entity_id=canonical_id,
                action="updated",
                before=before_canonical,
                after=after_canonical,
                actor=actor,
                details={"merged_into": absorbed_ids, **(details or {})},
                at=at,
            )

        # Re-point relationships.
        repointed = 0
        for abs_id in absorbed_ids:
            # Incoming and outgoing relationships.
            for direction in ("outgoing", "incoming"):
                rels = await self._relationships.active_at(
                    abs_id, direction=direction, limit=10_000
                )
                for rel in rels:
                    kwargs: dict[str, str] = {}
                    if rel.source_entity_id == abs_id:
                        kwargs["source_id"] = canonical_id
                    if rel.target_entity_id == abs_id:
                        kwargs["target_id"] = canonical_id
                    if kwargs:
                        await self._relationships.repoint(rel.id, **kwargs)
                        repointed += 1

        # Delete absorbed entities.
        for abs_id in absorbed_ids:
            before = snapshot(absorbed[abs_id])
            await self._entities.delete(abs_id)
            if self._lineage:
                self._lineage.record(
                    entity_id=abs_id,
                    action="absorbed",
                    before=before,
                    after=None,
                    actor=actor,
                    details={"merged_into": canonical_id, **(details or {})},
                    at=at,
                )

        log.info(
            "knowledge.resolution.merged",
            canonical_id=canonical_id,
            absorbed_ids=absorbed_ids,
            repointed=repointed,
        )
        return MergeResult(
            canonical_id=canonical_id,
            absorbed_ids=list(absorbed_ids),
            repointed_relationships=repointed,
            merged_aliases=list(merged_aliases),
            merged_evidence=merged_evidence,
            at=at,
        )

    # -- convenience ----------------------------------------------------------

    async def resolve(
        self,
        entity: EntitySchema,
        *,
        threshold: float = 0.7,
        actor: str | None = None,
        auto_merge: bool = True,
    ) -> list[MergeResult]:
        """High-level: find all candidates for ``entity`` and optionally merge.

        When ``auto_merge`` is True (default), all candidates above threshold
        are merged into ``entity`` in one pass. Returns the list of
        :class:`MergeResult` for each merge performed.
        """
        candidates = await self.find_candidates(entity, threshold=threshold)
        if not candidates:
            return []
        if not auto_merge:
            # Caller inspects candidates manually.
            return []
        absorbed_ids = [c.entity_b.id for c in candidates]
        result = await self.merge(
            entity.id, absorbed_ids, actor=actor, details={"auto": True}
        )
        return [result]
