"""Evidence records (NerveCenter spec Section 15).

Evidence is the provenance primitive of NerveCenter: every inference, decision,
entity, and relationship must cite captured evidence. An evidence record
immutably points to *where* a fact came from (a URL, file, transcript, tool
result, ...) and how trustworthy that source is.

Assumptions (spec Section 15 not present in the repository):
    - ``source_type`` is a classification literal over the kinds of sources a
      personal-intelligence core captures from.
    - ``content_hash`` stores the digest of the captured content (see
      :func:`schemas.base.content_hash`) so citations remain verifiable even if
      the original artifact moves or disappears.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import Record

#: Classification of the source an evidence record was captured from.
#:
#: The first eleven literals are capture-kind classifications; the spec
#: Section 15 evidence ``type`` values (``log``/``metric``/``event``/
#: ``source``/``diff``/``test``/``snapshot``) are included as additive
#: source types so that the citation index (``EvidenceService.list_by_source``)
#: can be filtered on them without schema rework (see
#: ``backend.orchestration`` which cites ``"event"`` sources by entity id).
EvidenceSourceType = Literal[
    "web_page",
    "document",
    "transcript",
    "message",
    "tool_result",
    "screenshot",
    "database_row",
    "file",
    "manual_note",
    "model_output",
    "log",
    "metric",
    "event",
    "source",
    "diff",
    "test",
    "snapshot",
    "other",
]


class Evidence(Record):
    """An immutable, citable provenance record."""

    source_type: EvidenceSourceType = Field(
        ...,
        description="Kind of source this evidence was captured from.",
    )
    source_ref: str = Field(
        ...,
        description="Locating reference for the source (URL, path, URI, or id).",
    )
    content: str | None = Field(
        default=None,
        description="Captured text/content excerpt; may be redacted per policy.",
    )
    content_hash: str | None = Field(
        default=None,
        description="SHA-256 digest of the captured content for verifiability.",
    )
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the content was captured (UTC).",
    )
    trust: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Trusted-source score (0..1) assigned at capture time.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Capture-time metadata (http status, offsets, tool name, ...).",
    )
    redacted: bool = Field(
        default=False,
        description="Whether the content was redacted by policy before storage.",
    )


class EvidenceCaptureRequest(BaseModel):
    """Request body for capturing a new evidence record (``POST /api/evidence``).

    ``content_hash`` is optional: it is derived from ``content`` at capture
    time and only accepted explicitly for reference-only captures (no stored
    content, e.g. redacted or artifact pointers) whose integrity must still
    be verifiable (spec Section 15: evidence records carry ``hash``).
    """

    source_type: EvidenceSourceType = Field(
        ...,
        description="Kind of source this evidence was captured from.",
    )
    source_ref: str = Field(
        ...,
        description="Locating reference for the source (URL, path, URI, or id).",
    )
    content: str | None = Field(
        default=None,
        description="Captured text/content excerpt; may be redacted per policy.",
    )
    content_hash: str | None = Field(
        default=None,
        description=(
            "SHA-256 digest of the content. Derived from ``content`` when "
            "absent; required for reference-only captures."
        ),
    )
    captured_at: datetime | None = Field(
        default=None,
        description="When the content was captured (UTC); defaults to now.",
    )
    trust: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Trusted-source score (0..1) assigned at capture time.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Capture-time metadata (http status, offsets, tool name, ...).",
    )
    redacted: bool = Field(
        default=False,
        description="Whether the content was redacted by policy before storage.",
    )
