"""Shared primitives for NerveCenter v0 data contracts.

This module defines the common building blocks used by every record in the
``schemas`` package:

- :data:`SCHEMA_VERSION` — the version tag stamped onto every record.
- :func:`content_hash` — deterministic SHA-256 hashing of a canonical JSON
  encoding, used for integrity verification.
- :class:`Record` — the base class for all persisted records. It provides a
  stable ``id``, a creation timestamp, a schema version, and an integrity
  ``hash`` field plus helpers to compute and verify it.
- :class:`TemporalWindow` — an optional ``[valid_from, valid_to]`` window that
  scopes when a fact or relationship holds true.

Assumptions (spec Sections 10-16 not present in the repository):
    These primitives are reconstructed from the NerveCenter README design
    principles (local-first, event-driven, evidence-based, schema-first,
    multi-client) and the v0 entity list. Field names chosen here form the
    stable backbone (``id``, ``hash``, ``created_at``) that every concrete
    entity relies on.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: Version tag stamped onto every record in the v0 contract set.
SCHEMA_VERSION = "v0"


def content_hash(payload: Any) -> str:
    """Return the SHA-256 hex digest of a canonical JSON encoding of ``payload``.

    Canonical encoding sorts keys and uses compact separators so that the digest
    is stable across serialization order and platform. Non-JSON-native values
    (e.g. ``datetime``) are coerced via their string form.

    Args:
        payload: Any JSON-serializable structure (typically a ``dict``).

    Returns:
        The 64-character lowercase hexadecimal SHA-256 digest.
    """
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Record(BaseModel):
    """Base class for every NerveCenter persisted record.

    Provides the common identity, provenance, and integrity fields:

    - ``id`` — a stable unique identifier (caller-supplied, typically a UUID).
    - ``created_at`` — when the record was first written (defaults to now, UTC).
    - ``schema_version`` — the contract version this record conforms to.
    - ``hash`` — an optional SHA-256 integrity digest. Call
        :meth:`fingerprint` to compute it and assign it here; call
        :meth:`verify_integrity` to confirm it still matches the content.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    id: str = Field(..., description="Stable unique identifier for the record (UUID string).")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of when the record was created (UTC).",
    )
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="Contract version this record conforms to.",
    )
    hash: str | None = Field(
        default=None,
        description="SHA-256 integrity digest of the record content; set via fingerprint().",
    )

    def fingerprint(self) -> str:
        """Compute the SHA-256 digest of this record's content (excluding ``hash``)."""
        data = self.model_dump(mode="json")
        data.pop("hash", None)
        return content_hash(data)

    def verify_integrity(self) -> bool:
        """Check the stored ``hash`` against a freshly computed fingerprint.

        Returns:
            ``True`` when the stored hash matches, or when no hash is set.
            ``False`` when a stored hash is present but does not match.
        """
        if self.hash is None:
            return True
        return self.hash == self.fingerprint()


class TemporalWindow(BaseModel):
    """Optional half-open interval ``[valid_from, valid_to)`` for time-scoped facts.

    Used by entities and relationships to express *when* a fact is or was true,
    separate from the moment it was observed (see ``asserted_at`` on relationships
    and ``created_at`` on records).
    """

    model_config = ConfigDict(extra="forbid")

    valid_from: datetime | None = Field(
        default=None,
        description="Inclusive lower bound of the validity window (UTC).",
    )
    valid_to: datetime | None = Field(
        default=None,
        description="Exclusive upper bound of the validity window (UTC).",
    )
