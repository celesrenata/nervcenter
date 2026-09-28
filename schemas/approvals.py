"""Approval records (NerveCenter spec Section 10-16).

An *Approval* is a human (or policy) sign-off on a :class:`PlannedChange`.
Approvals carry the approver identity, decision, rationale, and optional
expiry — the audit trail that justifies why a change was (or was not) applied.

Assumptions (spec not present in the repository):
    - ``approver_type`` distinguishes human vs policy vs orchestrator vs agent.
    - ``decision`` is the terminal verdict (approved / denied / no_response).
    - ``expires_at`` scopes the approval window; after it the planned change
      cannot be applied via this approval.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from .base import Record

#: Who is authorizing the change.
ApproverType = Literal["human", "policy", "orchestrator", "agent"]

#: Terminal verdict of an approval.
ApprovalDecision = Literal["approved", "denied", "no_response"]


class Approval(Record):
    """A sign-off (or refusal) on a :class:`PlannedChange`."""

    planned_change_id: str = Field(
        ...,
        description="Id of the :class:`PlannedChange` this approval applies to.",
    )
    approver_type: ApproverType = Field(
        ...,
        description="Kind of approver (human, policy, orchestrator, agent).",
    )
    approver_id: str = Field(
        ...,
        description="Identifier of the approver (user id, policy rule id, agent id, ...).",
    )
    decision: ApprovalDecision = Field(
        ...,
        description="Terminal verdict.",
    )
    rationale: str | None = Field(
        default=None,
        description="Explanation of the verdict, if any.",
    )
    decided_at: datetime | None = Field(
        default=None,
        description="When the verdict was issued (UTC).",
    )
    requested_at: datetime | None = Field(
        default=None,
        description="When the approval was first requested (UTC).",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="End of the approval validity window (UTC).",
    )
    scope: str | None = Field(
        default=None,
        description="Optional scope constraint (e.g. 'only while device is on the same network').",
    )
