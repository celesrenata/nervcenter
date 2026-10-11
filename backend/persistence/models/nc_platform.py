"""ORM models for the canonical resource platform (NC-SPEC-2026-010 Phase 1).

This module maps the C1 contracts freeze (NC-WS-001) onto Postgres, backing
the Pydantic contract pack in ``schemas/nc_platform.py``:

- :class:`NCResourceRow`          — ``nc_resources`` (canonical resources).
- :class:`NCConnectorInstanceRow` — ``nc_connector_instances``.
- :class:`NCResourceAliasRow`     — ``nc_resource_aliases`` (ADR-0001).
- :class:`NCResourceRelationRow`  — ``nc_resource_relations``.
- :class:`NCResourceSnapshotRow`  — ``nc_resource_snapshots``.
- :class:`NCPrincipalRow`         — ``nc_principals``.
- :class:`NCPolicyRow`            — ``nc_policies``.
- :class:`NCApprovalRow`          — ``nc_approvals``.

Naming note
-----------
The Pydantic contract classes are named ``NCResource`` etc.; the ORM rows
carry a ``Row`` suffix so both can coexist in one import namespace without
shadowing each other.

Tombstone semantics (NC-REQ-008, ADR-0001)
-----------------------------------------
Resource rows are **never deleted** by connector behavior. A resource that
disappears from its provider is transitioned to ``sync_status = 'tombstoned'``;
the row and all of its alias rows remain so the canonical ``nc://`` URI keeps
resolving. Physical row deletion is a reconciliation/admin operation only,
never something a connector triggers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Jsonb, UUIDv4


class NCResourceRow(Base):
    """Canonical resource row: one real-world thing = one canonical URI.

    Table ``nc_resources`` columns
    ------------------------------
    - ``id`` (UUID) — record row id (immutable, generated).
    - ``created_at`` / ``updated_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``resource_id`` (text, unique) — stable business id (``res_`` + ULID).
    - ``uri`` (text, unique) — canonical ``nc://`` URI (NC-REQ-001).
    - ``namespace`` (text) — isolation boundary (personal/shared/system/<task>).
    - ``connector_instance_id`` (text) — registering connector instance.
    - ``provider`` (text) — connector provider id.
    - ``provider_resource_id`` (text) — provider-native id, path-escaped.
    - ``kind`` (text) — connector kind id.
    - ``display_name`` (text) — display only, never identity.
    - ``capabilities`` (JSONB array of text) — declared capabilities.
    - ``labels`` (JSONB) — structured labels.
    - ``data_classification`` (text) — PUBLIC | HOME_PRIVATE | PERSONAL_PRIVATE
      | FINANCIAL | HEALTH_SENSITIVE | BIOMETRIC | SECRET.
    - ``observed_state`` (JSONB) — last observed state.
    - ``observed_at`` (timestamptz, nullable) — when observed_state was captured.
    - ``desired_state`` (JSONB) — last approved desired state.
    - ``sync_status`` (text) — current | stale | failed | tombstoned.
    - ``owner_principal_id`` (text, nullable) — owning :class:`NCPrincipalRow`.
    - ``source_evidence`` (JSONB array of text) — evidence citations.

    Indexes
    -------
    - ``ix_nc_resources_resource_id`` (unique) — business-id lookup.
    - ``ix_nc_resources_uri`` (unique) — canonical URI lookup (NC-REQ-001).
    - ``ix_nc_resources_provider_resource`` (unique pair) — provider-native
      identity reconciliation (exactly one canonical identity per provider-
      native id, NC-MS-001).
    - ``ix_nc_resources_namespace_sync`` — namespace-filtered sync sweeps.
    - ``ix_nc_resources_connector_instance`` — per-instance resource listing.
    - ``ix_nc_resources_owner`` — owner-centric reverse lookup.
    """

    __tablename__ = "nc_resources"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    resource_id: Mapped[str] = mapped_column(String(32), nullable=False)
    uri: Mapped[str] = mapped_column(String(512), nullable=False)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_instance_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("nc_connector_instances.instance_id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(Jsonb, default=dict, nullable=False)
    data_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_state: Mapped[dict[str, Any]] = mapped_column(
        Jsonb, default=dict, nullable=False
    )
    observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    desired_state: Mapped[dict[str, Any]] = mapped_column(
        Jsonb, default=dict, nullable=False
    )
    sync_status: Mapped[str] = mapped_column(
        String(16), default="current", nullable=False
    )
    owner_principal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_evidence: Mapped[list[str]] = mapped_column(
        Jsonb, default=list, nullable=False
    )

    __table_args__ = (
        Index("ix_nc_resources_resource_id", "resource_id", unique=True),
        Index("ix_nc_resources_uri", "uri", unique=True),
        Index(
            "ix_nc_resources_provider_resource",
            "provider",
            "provider_resource_id",
            unique=True,
        ),
        Index("ix_nc_resources_namespace_sync", "namespace", "sync_status"),
        Index("ix_nc_resources_connector_instance", "connector_instance_id"),
        Index("ix_nc_resources_owner", "owner_principal_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCResourceRow resource_id={self.resource_id!r} "
            f"uri={self.uri!r} sync_status={self.sync_status!r}>"
        )


class NCConnectorInstanceRow(Base):
    """Deployed connector of a known kind (NC-CAP-001 / NC-CAP-002).

    Table ``nc_connector_instances`` columns
    ----------------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` / ``updated_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``instance_id`` (text, unique) — stable id (``conn_`` + ULID).
    - ``provider`` (text) — connector provider id.
    - ``credentials_ref`` (text) — vaulted-credential reference (never the
      material; NC-CAP-008).
    - ``scopes`` (JSONB array of text) — granted provider scopes.
    - ``rate_limit`` (JSONB) — negotiated rate quota.
    - ``read_only`` (boolean) — degraded read-only/stale flag (NC-REQ-008).
    - ``health`` (text) — healthy | degraded | unreachable | lost.

    Indexes
    -------
    - ``ix_nc_connector_instances_instance_id`` (unique).
    - ``ix_nc_connector_instances_provider`` — provider-scoped listing.
    """

    __tablename__ = "nc_connector_instances"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    instance_id: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    credentials_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)
    rate_limit: Mapped[dict[str, Any]] = mapped_column(
        Jsonb, default=dict, nullable=False
    )
    read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    health: Mapped[str] = mapped_column(String(16), default="healthy", nullable=False)

    __table_args__ = (
        Index(
            "ix_nc_connector_instances_instance_id", "instance_id", unique=True
        ),
        Index("ix_nc_connector_instances_provider", "provider"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCConnectorInstanceRow instance_id={self.instance_id!r} "
            f"provider={self.provider!r} health={self.health!r}>"
        )


class NCResourceAliasRow(Base):
    """Alias row: non-canonical identity -> canonical URI (ADR-0001).

    Table ``nc_resource_aliases`` columns
    -------------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``alias_uri`` (text, unique) — the non-canonical URI that resolves.
    - ``resource_id`` (text) — canonical resource it resolves to (FK).
    - ``kind`` (text) — alias provenance class (canonical | task | user).
    - ``namespace`` (text) — namespace the alias lives in.
    - ``created_by_principal_id`` (text, nullable) — who registered it.

    Tombstone note: alias rows of a tombstoned resource are kept, so the
    alias keeps resolving to the (tombstoned) canonical row — never deleted
    alongside the resource.

    Indexes
    -------
    - ``ix_nc_resource_aliases_alias_uri`` (unique) — alias -> canonical.
    - ``ix_nc_resource_aliases_resource`` — canonical -> alias listing.
    """

    __tablename__ = "nc_resource_aliases"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    alias_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    resource_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("nc_resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    __table_args__ = (
        Index("ix_nc_resource_aliases_alias_uri", "alias_uri", unique=True),
        Index("ix_nc_resource_aliases_resource", "resource_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCResourceAliasRow alias_uri={self.alias_uri!r} "
            f"resource_id={self.resource_id!r}>"
        )


class NCResourceRelationRow(Base):
    """Directed relation between two canonical resources (NC-CAP-006).

    Table ``nc_resource_relations`` columns
    --------------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``source_resource_id`` / ``target_resource_id`` (text) — FK to
      ``nc_resources.resource_id``.
    - ``relation_type`` (text) — declared relation type (never inferred).
    - ``confidence`` (float) — 0..1 evidence strength.
    - ``evidence`` (JSONB array of text) — evidence citations.

    Indexes
    -------
    - ``ix_nc_resource_relations_source_target_type`` (unique triple).
    - ``ix_nc_resource_relations_source`` / ``ix_nc_resource_relations_target``.
    """

    __tablename__ = "nc_resource_relations"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    source_resource_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("nc_resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    target_resource_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("nc_resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(Jsonb, default=list, nullable=False)

    __table_args__ = (
        Index(
            "ix_nc_resource_relations_source_target_type",
            "source_resource_id",
            "target_resource_id",
            "relation_type",
            unique=True,
        ),
        Index("ix_nc_resource_relations_source", "source_resource_id"),
        Index("ix_nc_resource_relations_target", "target_resource_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCResourceRelationRow "
            f"source={self.source_resource_id!r} "
            f"target={self.target_resource_id!r} "
            f"relation_type={self.relation_type!r}>"
        )


class NCResourceSnapshotRow(Base):
    """Point-in-time snapshot of a resource's observed state.

    Table ``nc_resource_snapshots`` columns
    --------------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``resource_id`` (text) — FK to ``nc_resources.resource_id``.
    - ``state`` (JSONB) — the captured state.
    - ``captured_at`` (timestamptz) — snapshot time.
    - ``connector_instance_id`` (text, nullable) — capturing instance.
    - ``dedup_key`` (text, unique, nullable) — dedup-relevant column: at most
      one snapshot per dedup key, so re-capturing the same provider state
      does not create a duplicate row.

    Snapshots are immutable: no ``updated_at`` column.

    Indexes
    -------
    - ``ix_nc_resource_snapshots_resource_time`` — history listing.
    - ``ix_nc_resource_snapshots_dedup_key`` (unique) — dedup enforcement.
    """

    __tablename__ = "nc_resource_snapshots"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    resource_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("nc_resources.resource_id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[dict[str, Any]] = mapped_column(Jsonb, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connector_instance_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("nc_connector_instances.instance_id", ondelete="SET NULL"),
        nullable=True,
    )
    dedup_key: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index(
            "ix_nc_resource_snapshots_resource_time", "resource_id", "captured_at"
        ),
        Index("ix_nc_resource_snapshots_dedup_key", "dedup_key", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<NCResourceSnapshotRow resource_id={self.resource_id!r} "
            f"captured_at={self.captured_at!r}>"
        )


class NCPrincipalRow(Base):
    """Policy subject row (NC-CAP-007).

    Table ``nc_principals`` columns
    -------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` / ``updated_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``principal_id`` (text, unique) — stable id (``prn_`` + ULID).
    - ``kind`` (text) — human | agent | workflow | function | connector |
      device | api_client.
    - ``display_name`` (text) — display only.
    - ``namespace`` (text) — namespace the principal is scoped to.
    - ``hashed_token_ref`` (text, nullable) — hashed scoped-token reference
      (never the token).

    Indexes
    -------
    - ``ix_nc_principals_principal_id`` (unique).
    - ``ix_nc_principals_namespace`` — namespace-scoped listing.
    """

    __tablename__ = "nc_principals"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    principal_id: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    hashed_token_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index("ix_nc_principals_principal_id", "principal_id", unique=True),
        Index("ix_nc_principals_namespace", "namespace"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCPrincipalRow principal_id={self.principal_id!r} "
            f"kind={self.kind!r} namespace={self.namespace!r}>"
        )


class NCPolicyRow(Base):
    """Cedar-style policy row (NC-CAP-007, ADR-0003).

    Table ``nc_policies`` columns
    -----------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` / ``updated_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``policy_id`` (text) — stable id (``pol_`` + ULID).
    - ``effect`` (text) — ALLOW | DENY (explicit DENY precedence, default DENY).
    - ``principal_match`` (text) — principal match expression.
    - ``action_match`` (text) — action match expression.
    - ``resource_match`` (text) — resource match (URI or URI prefix).
    - ``condition`` (text, nullable) — CEL-spirit condition.
    - ``priority`` (integer) — evaluation order among otherwise-equivalent
      policies (higher first).
    - ``version`` (integer) — document version; re-issued on every change.

    Indexes
    -------
    - ``ix_nc_policies_policy_id`` (unique per policy id).
    - ``ix_nc_policies_policy_version`` (unique pair) — one row per
      policy/version, so re-issued documents are versioned, not overwritten.
    """

    __tablename__ = "nc_policies"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    policy_id: Mapped[str] = mapped_column(String(32), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False)
    principal_match: Mapped[str] = mapped_column(String(256), nullable=False)
    action_match: Mapped[str] = mapped_column(String(256), nullable=False)
    resource_match: Mapped[str] = mapped_column(String(512), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("ix_nc_policies_policy_id", "policy_id", unique=True),
        Index(
            "ix_nc_policies_policy_version", "policy_id", "version", unique=True
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NCPolicyRow policy_id={self.policy_id!r} effect={self.effect!r} "
            f"version={self.version!r}>"
        )


class NCApprovalRow(Base):
    """Approval row scoped to an immutable payload (NC-CAP-015).

    Table ``nc_approvals`` columns
    ------------------------------
    - ``id`` (UUID) — record row id.
    - ``created_at`` / ``updated_at`` (timestamptz) — record provenance.
    - ``schema_version`` (text) — always "v0" for this version.
    - ``approval_id`` (text, unique) — stable id (``app_`` + ULID).
    - ``execution_id`` (text) — workflow execution that requested it.
    - ``proposed_action`` (JSONB) — exact action (name + arguments).
    - ``target_uri`` (text) — canonical ``nc://`` URI of the target.
    - ``payload_hash`` (text) — SHA-256 of the immutable payload at request
      time; a mismatch invalidates the approval.
    - ``expires_at`` (timestamptz) — validity window end.
    - ``state`` (text) — WAITING_FOR_APPROVAL | APPROVED | DENIED | EXPIRED |
      INVALIDATED.

    Indexes
    -------
    - ``ix_nc_approvals_approval_id`` (unique).
    - ``ix_nc_approvals_execution`` — per-execution approval listing.
    """

    __tablename__ = "nc_approvals"

    id: Mapped[UUIDv4]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schema_version: Mapped[str] = mapped_column(String(16), default="v0")

    approval_id: Mapped[str] = mapped_column(String(32), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action: Mapped[dict[str, Any]] = mapped_column(Jsonb, nullable=False)
    target_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(
        String(24), default="WAITING_FOR_APPROVAL", nullable=False
    )

    __table_args__ = (
        Index("ix_nc_approvals_approval_id", "approval_id", unique=True),
        Index("ix_nc_approvals_execution", "execution_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NCApprovalRow approval_id={self.approval_id!r} "
            f"state={self.state!r}>"
        )
