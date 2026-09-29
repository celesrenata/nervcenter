"""Claim and Decision records (NerveCenter spec Sections 16 and 10/15).

A *claim* is a proposition about the world the core has formed from evidence —
the unit that is supported, contradicted, or superseded over time. A *decision*
is a claim the system acted on: it records what was chosen, why, and which
evidence justified it.

Assumptions (spec Section 16 not present in the repository):
    - ``status`` is a lifecycle literal (open → supported/contradicted →
      superseded or rejected).
    - ``Decision`` reuses the claim structure and adds the executed ``action``,
      the rationale, and a link to the resulting :class:`PlannedChange`/Task ids.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Lifecycle state of a claim.
ClaimStatus = Literal["open", "supported", "contradicted", "superseded", "rejected"]

#: How a decision was reached.
DecisionMechanism = Literal["heuristic", "model_inference", "human", "policy", "orchestrator"]


class Claim(Record):
    """A proposition formed from evidence, with a lifecycle and confidence."""

    statement: str = Field(
        ...,
        description="The claim, stated as a single sentence.",
    )
    subject_entity_id: str | None = Field(
        default=None,
        description="Primary entity the claim is about, if any.",
    )
    status: ClaimStatus = Field(
        default="open",
        description="Lifecycle state of the claim.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence (0..1) that the claim is true.",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records supporting the claim.",
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records contradicting the claim.",
    )
    derived_from_claims: list[str] = Field(
        default_factory=list,
        description="Ids of other claims this claim was inferred from.",
    )
    supersedes_claim_id: str | None = Field(
        default=None,
        description="Id of the earlier claim this one replaces, when superseded.",
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, claim-specific data (values, ranges, tags, ...).",
    )


class Decision(Record):
    """A claim the system acted on, with rationale and execution links."""

    claim_id: str = Field(
        ...,
        description="Id of the :class:`Claim` this decision was made on.",
    )
    statement: str = Field(
        ...,
        description="Restatement of the decision taken.",
    )
    mechanism: DecisionMechanism = Field(
        ...,
        description="How the decision was reached.",
    )
    rationale: str | None = Field(
        default=None,
        description="Explainable rationale for the decision.",
    )
    action: str = Field(
        default="no_action",
        description="Machine-readable action identifier chosen (e.g. 'task.schedule').",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records justifying the decision.",
    )
    planned_change_id: str | None = Field(
        default=None,
        description="Id of the resulting :class:`PlannedChange`, if one was emitted.",
    )
    task_id: str | None = Field(
        default=None,
        description="Id of the resulting :class:`Task`, if one was scheduled.",
    )
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the decision was made (UTC).",
    )
