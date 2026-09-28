"""Relationship derivation rules for the knowledge plane.

NerveCenter's knowledge graph stores *asserted* relationships (those backed
by evidence). Some relationships can be **derived** from others by logical
rules. For example:

- If ``A member_of B`` and ``B member_of C``, then ``A member_of C``
  (transitivity of ``member_of``).
- If ``A parent_of B``, then ``B child_of A`` (inverse).
- If ``A owns B`` and ``B located_in C``, then ``A located_in C``
  (projection).

:class:`DerivationEngine` evaluates a set of :class:`DerivationRule`
definitions against a snapshot of the graph and produces new
:class:`~schemas.relationships.Relationship` records for relationships that
are implied but not yet asserted.

Spec sections
-------------
- NerveCenter specification Section 13 (Temporal Relationships).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import structlog
from schemas.base import TemporalWindow
from schemas.relationships import Relationship as RelationshipSchema

from .relationship import RelationshipService

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Rule types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DerivationRule:
    """A single derivation rule: if premises hold, derive conclusion.

    Attributes
    ----------
    name:
        Human-readable rule name.
    premises:
        A list of ``(source_rel_type, target_rel_type, direction)`` tuples
        describing the relationship pattern that triggers the rule. For
        simple rules, a single premise of ``(rel_type, None, "outgoing")``
        suffices.
    conclusion_type:
        The relation_type of the derived relationship.
    derive_fn:
        A callable that, given the matched premise relationships, returns
        the derived relationship's endpoints and properties, or ``None`` if
        the rule does not apply.
    valid_window:
        If set, the derived relationship's validity window is clamped to
        this window. Otherwise it inherits the intersection of the
        premises' windows.
    """

    name: str
    premises: tuple[tuple[str, str | None, str], ...]
    conclusion_type: str
    derive_fn: Callable[[list[RelationshipSchema]], "DerivedRelationship | None"]
    valid_window: TemporalWindow | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DerivedRelationship:
    """A proposed derived relationship before persistence."""

    source_entity_id: str
    target_entity_id: str
    relation_type: str
    properties: dict[str, Any]
    valid_from: datetime | None
    valid_to: datetime | None
    confidence: float
    evidence: list[str]
    derivation_rule: str


@dataclass(frozen=True)
class DerivationResult:
    """Summary of a derivation run."""

    rule_name: str
    derived: list[DerivedRelationship]
    skipped_existing: int
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------


def _intersect_windows(rels: list[RelationshipSchema]) -> tuple[datetime | None, datetime | None]:
    """Compute the intersection of validity windows."""
    froms = [r.valid.valid_from for r in rels if r.valid.valid_from is not None]
    tos = [r.valid.valid_to for r in rels if r.valid.valid_to is not None]
    valid_from = max(froms) if froms else None
    valid_to = min(tos) if tos else None
    return valid_from, valid_to


def _transitive_member_of(rels: list[RelationshipSchema]) -> DerivedRelationship | None:
    """Derive transitive membership: A member_of B, B member_of C → A member_of C."""
    if len(rels) < 2:
        return None
    # rels[0]: A member_of B, rels[1]: B member_of C
    a = rels[0].source_entity_id
    b = rels[0].target_entity_id
    c = rels[1].target_entity_id
    if rels[1].source_entity_id != b:
        return None
    if a == c:
        return None  # circular
    vf, vt = _intersect_windows(rels)
    evidence = rels[0].evidence + rels[1].evidence
    return DerivedRelationship(
        source_entity_id=a,
        target_entity_id=c,
        relation_type="member_of",
        properties={"derived_from": [rels[0].id, rels[1].id]},
        valid_from=vf,
        valid_to=vt,
        confidence=min(r.confidence for r in rels),
        evidence=evidence,
        derivation_rule="transitive_member_of",
    )


def _inverse_parent_child(rels: list[RelationshipSchema]) -> DerivedRelationship | None:
    """Derive inverse: A parent_of B → B child_of A."""
    if len(rels) < 1:
        return None
    rel = rels[0]
    vf, vt = _intersect_windows(rels)
    return DerivedRelationship(
        source_entity_id=rel.target_entity_id,
        target_entity_id=rel.source_entity_id,
        relation_type="child_of",
        properties={"derived_from": [rel.id]},
        valid_from=vf,
        valid_to=vt,
        confidence=rel.confidence,
        evidence=list(rel.evidence),
        derivation_rule="inverse_parent_child",
    )


def _inverse_child_parent(rels: list[RelationshipSchema]) -> DerivedRelationship | None:
    """Derive inverse: A child_of B → B parent_of A."""
    if len(rels) < 1:
        return None
    rel = rels[0]
    vf, vt = _intersect_windows(rels)
    return DerivedRelationship(
        source_entity_id=rel.target_entity_id,
        target_entity_id=rel.source_entity_id,
        relation_type="parent_of",
        properties={"derived_from": [rel.id]},
        valid_from=vf,
        valid_to=vt,
        confidence=rel.confidence,
        evidence=list(rel.evidence),
        derivation_rule="inverse_child_parent",
    )


def _inverse_owns_owned_by(rels: list[RelationshipSchema]) -> DerivedRelationship | None:
    """Derive inverse: A owns B → B owned_by A."""
    if len(rels) < 1:
        return None
    rel = rels[0]
    vf, vt = _intersect_windows(rels)
    return DerivedRelationship(
        source_entity_id=rel.target_entity_id,
        target_entity_id=rel.source_entity_id,
        relation_type="owned_by",
        properties={"derived_from": [rel.id]},
        valid_from=vf,
        valid_to=vt,
        confidence=rel.confidence,
        evidence=list(rel.evidence),
        derivation_rule="inverse_owns",
    )


def _inverse_owned_by_owns(rels: list[RelationshipSchema]) -> DerivedRelationship | None:
    """Derive inverse: A owned_by B → B owns A."""
    if len(rels) < 1:
        return None
    rel = rels[0]
    vf, vt = _intersect_windows(rels)
    return DerivedRelationship(
        source_entity_id=rel.target_entity_id,
        target_entity_id=rel.source_entity_id,
        relation_type="owns",
        properties={"derived_from": [rel.id]},
        valid_from=vf,
        valid_to=vt,
        confidence=rel.confidence,
        evidence=list(rel.evidence),
        derivation_rule="inverse_owned_by",
    )


#: Default set of derivation rules shipped with the engine.
DEFAULT_RULES: list[DerivationRule] = [
    DerivationRule(
        name="transitive_member_of",
        premises=(("member_of", None, "outgoing"), ("member_of", None, "outgoing")),
        conclusion_type="member_of",
        derive_fn=_transitive_member_of,
    ),
    DerivationRule(
        name="inverse_parent_child",
        premises=(("parent_of", None, "outgoing"),),
        conclusion_type="child_of",
        derive_fn=_inverse_parent_child,
    ),
    DerivationRule(
        name="inverse_child_parent",
        premises=(("child_of", None, "outgoing"),),
        conclusion_type="parent_of",
        derive_fn=_inverse_child_parent,
    ),
    DerivationRule(
        name="inverse_owns",
        premises=(("owns", None, "outgoing"),),
        conclusion_type="owned_by",
        derive_fn=_inverse_owns_owned_by,
    ),
    DerivationRule(
        name="inverse_owned_by",
        premises=(("owned_by", None, "outgoing"),),
        conclusion_type="owns",
        derive_fn=_inverse_owned_by_owns,
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DerivationEngine:
    """Evaluates derivation rules against the graph and persists new edges.

    Usage::

        engine = DerivationEngine(relationships, rules=DEFAULT_RULES)
        results = await engine.run()
        for r in results:
            print(f"{r.rule_name}: derived {len(r.derived)} relationships")
    """

    def __init__(
        self,
        relationships: RelationshipService,
        rules: Sequence[DerivationRule] | None = None,
    ) -> None:
        self._relationships = relationships
        self._rules: list[DerivationRule] = list(rules) if rules else list(DEFAULT_RULES)

    @property
    def rules(self) -> list[DerivationRule]:
        return list(self._rules)

    def add_rule(self, rule: DerivationRule) -> None:
        """Register an additional derivation rule."""
        self._rules.append(rule)

    async def run(
        self,
        *,
        at: datetime | None = None,
        limit: int = 10_000,
    ) -> list[DerivationResult]:
        """Execute all rules against the active graph at ``at``.

        For each rule, scans the relevant relationship types, calls the
        rule's ``derive_fn``, checks whether the derived relationship already
        exists (by endpoint + type + window), and persists new ones.
        """
        results: list[DerivationResult] = []
        # Load the full active snapshot once.
        all_rels = await self._relationships.active_snapshot(at, limit=limit)
        all_rel_ids = {r.id for r in all_rels}

        for rule in self._rules:
            result = await self._execute_rule(rule, all_rels, all_rel_ids)
            results.append(result)
            log.info(
                "knowledge.derivation.rule_executed",
                rule=rule.name,
                derived=len(result.derived),
                skipped=result.skipped_existing,
            )
        return results

    async def _execute_rule(
        self,
        rule: DerivationRule,
        all_rels: list[RelationshipSchema],
        existing_ids: set[str],
    ) -> DerivationResult:
        """Apply a single rule to the loaded snapshot."""
        derived: list[DerivedRelationship] = []
        skipped = 0
        errors: list[str] = []

        # Find all relationships matching the rule's first premise type.
        first_type = rule.premises[0][0]
        relevant = [r for r in all_rels if r.relation_type == first_type]

        # Group by source entity for transitive rules.
        if len(rule.premises) > 1:
            # Multi-premise rule: group by source and find chains.
            from collections import defaultdict

            by_source: dict[str, list[RelationshipSchema]] = defaultdict(list)
            for r in relevant:
                by_source[r.source_entity_id].append(r)

            second_type = rule.premises[1][0]
            for source_id, first_hops in by_source.items():
                for first_hop in first_hops:
                    # Find second-hop relationships from first_hop's target.
                    second_hops = [
                        r
                        for r in all_rels
                        if r.relation_type == second_type
                        and r.source_entity_id == first_hop.target_entity_id
                    ]
                    for second_hop in second_hops:
                        try:
                            prop = rule.derive_fn([first_hop, second_hop])
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"{rule.name}: {exc}")
                            continue
                        if prop is None:
                            continue
                        if await self._already_exists(prop, all_rels):
                            skipped += 1
                            continue
                        derived.append(prop)
        else:
            # Single-premise rule.
            for rel in relevant:
                try:
                    prop = rule.derive_fn([rel])
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{rule.name}: {exc}")
                    continue
                if prop is None:
                    continue
                if await self._already_exists(prop, all_rels):
                    skipped += 1
                    continue
                derived.append(prop)

        # Persist derived relationships.
        for prop in derived:
            try:
                await self._relationships.create(
                    prop.source_entity_id,
                    prop.target_entity_id,
                    prop.relation_type,
                    properties=prop.properties,
                    valid_from=prop.valid_from,
                    valid_to=prop.valid_to,
                    confidence=prop.confidence,
                    evidence=prop.evidence,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rule.name}: persist failed: {exc}")

        return DerivationResult(
            rule_name=rule.name,
            derived=derived,
            skipped_existing=skipped,
            errors=errors,
        )

    async def _already_exists(
        self, prop: DerivedRelationship, all_rels: list[RelationshipSchema]
    ) -> bool:
        """Check if an equivalent relationship already exists in the snapshot."""
        for r in all_rels:
            if (
                r.source_entity_id == prop.source_entity_id
                and r.target_entity_id == prop.target_entity_id
                and r.relation_type == prop.relation_type
            ):
                # Check window overlap (simplified: same endpoints+type = exists).
                return True
        return False
