"""Canonical resource platform tables (NC-SPEC-2026-010, C1 contracts freeze).

Adds the eight tables backing the Phase-1 canonical resource platform and the
Pydantic contract pack in ``schemas/nc_platform.py``:

- ``nc_connector_instances`` — deployed connectors (NC-CAP-001/002).
- ``nc_resources``           — canonical resources (one URI per real thing,
  NC-REQ-001); never physically deleted — disappearance is a
  ``sync_status='tombstoned'`` transition (NC-REQ-008, ADR-0001).
- ``nc_resource_aliases``     — non-canonical identity -> canonical URI
  (ADR-0001); alias rows persist through a resource's tombstone.
- ``nc_resource_relations``   — declared relations between resources
  (NC-CAP-006).
- ``nc_resource_snapshots``   — point-in-time state captures, immutable,
  deduped by ``dedup_key``.
- ``nc_principals``           — policy subjects (NC-CAP-007).
- ``nc_policies``             — Cedar-style policy documents (ADR-0003),
  versioned per policy.
- ``nc_approvals``            — approvals scoped to an immutable payload
  (NC-CAP-015).

Conventions match :mod:`001_initial` / :mod:`002_auth` / :mod:`004_incidents_agents`:
identifier columns are ``sa.String()`` (the ORM's ``UUID(as_uuid=False)`` maps
cleanly onto them), JSONB columns use ``postgresql.JSONB(astext_type=sa.Text())``
so the migration stays portable to the SQLite scratch databases used by the
test suite, and indexes follow the ``ix_<table>_<column>`` naming.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005_nc_platform"
down_revision = "004_incidents_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # nc_connector_instances (no FK dependencies; must precede nc_resources).
    op.create_table(
        "nc_connector_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("instance_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("credentials_ref", sa.String(length=256), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "rate_limit",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("health", sa.String(length=16), nullable=False, server_default="healthy"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nc_connector_instances_instance_id",
        "nc_connector_instances",
        ["instance_id"],
        unique=True,
    )
    op.create_index(
        "ix_nc_connector_instances_provider",
        "nc_connector_instances",
        ["provider"],
        unique=False,
    )

    # nc_resources (references nc_connector_instances).
    op.create_table(
        "nc_resources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("resource_id", sa.String(length=32), nullable=False),
        sa.Column("uri", sa.String(length=512), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("connector_instance_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_resource_id", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("data_classification", sa.String(length=32), nullable=False),
        sa.Column(
            "observed_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "desired_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("sync_status", sa.String(length=16), nullable=False, server_default="current"),
        sa.Column("owner_principal_id", sa.String(length=32), nullable=True),
        sa.Column(
            "source_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"],
            ["nc_connector_instances.instance_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_nc_resources_resource_id", "nc_resources", ["resource_id"], unique=True
    )
    op.create_index("ix_nc_resources_uri", "nc_resources", ["uri"], unique=True)
    op.create_index(
        "ix_nc_resources_provider_resource",
        "nc_resources",
        ["provider", "provider_resource_id"],
        unique=True,
    )
    op.create_index(
        "ix_nc_resources_namespace_sync",
        "nc_resources",
        ["namespace", "sync_status"],
        unique=False,
    )
    op.create_index(
        "ix_nc_resources_connector_instance",
        "nc_resources",
        ["connector_instance_id"],
        unique=False,
    )
    op.create_index(
        "ix_nc_resources_owner", "nc_resources", ["owner_principal_id"], unique=False
    )

    # nc_resource_aliases (references nc_resources).
    op.create_table(
        "nc_resource_aliases",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("alias_uri", sa.String(length=512), nullable=False),
        sa.Column("resource_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("created_by_principal_id", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["nc_resources.resource_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_nc_resource_aliases_alias_uri",
        "nc_resource_aliases",
        ["alias_uri"],
        unique=True,
    )
    op.create_index(
        "ix_nc_resource_aliases_resource",
        "nc_resource_aliases",
        ["resource_id"],
        unique=False,
    )

    # nc_resource_relations (references nc_resources twice).
    op.create_table(
        "nc_resource_relations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("source_resource_id", sa.String(length=32), nullable=False),
        sa.Column("target_resource_id", sa.String(length=32), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_resource_id"],
            ["nc_resources.resource_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_resource_id"],
            ["nc_resources.resource_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_nc_resource_relations_source_target_type",
        "nc_resource_relations",
        ["source_resource_id", "target_resource_id", "relation_type"],
        unique=True,
    )
    op.create_index(
        "ix_nc_resource_relations_source",
        "nc_resource_relations",
        ["source_resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_nc_resource_relations_target",
        "nc_resource_relations",
        ["target_resource_id"],
        unique=False,
    )

    # nc_resource_snapshots (references nc_resources and nc_connector_instances).
    op.create_table(
        "nc_resource_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("resource_id", sa.String(length=32), nullable=False),
        sa.Column(
            "state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connector_instance_id", sa.String(length=32), nullable=True),
        sa.Column("dedup_key", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["nc_resources.resource_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connector_instance_id"],
            ["nc_connector_instances.instance_id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_nc_resource_snapshots_resource_time",
        "nc_resource_snapshots",
        ["resource_id", "captured_at"],
        unique=False,
    )
    op.create_index(
        "ix_nc_resource_snapshots_dedup_key",
        "nc_resource_snapshots",
        ["dedup_key"],
        unique=True,
    )

    # nc_principals.
    op.create_table(
        "nc_principals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("principal_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("hashed_token_ref", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nc_principals_principal_id",
        "nc_principals",
        ["principal_id"],
        unique=True,
    )
    op.create_index(
        "ix_nc_principals_namespace", "nc_principals", ["namespace"], unique=False
    )

    # nc_policies.
    op.create_table(
        "nc_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("policy_id", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=8), nullable=False),
        sa.Column("principal_match", sa.String(length=256), nullable=False),
        sa.Column("action_match", sa.String(length=256), nullable=False),
        sa.Column("resource_match", sa.String(length=512), nullable=False),
        sa.Column("condition", sa.String(length=1024), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nc_policies_policy_id", "nc_policies", ["policy_id"], unique=True
    )
    op.create_index(
        "ix_nc_policies_policy_version",
        "nc_policies",
        ["policy_id", "version"],
        unique=True,
    )

    # nc_approvals.
    op.create_table(
        "nc_approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("approval_id", sa.String(length=32), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column(
            "proposed_action",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("target_uri", sa.String(length=512), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "state",
            sa.String(length=24),
            nullable=False,
            server_default="WAITING_FOR_APPROVAL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nc_approvals_approval_id", "nc_approvals", ["approval_id"], unique=True
    )
    op.create_index(
        "ix_nc_approvals_execution", "nc_approvals", ["execution_id"], unique=False
    )


def downgrade() -> None:
    # Reverse dependency order: drop children before the tables they reference.
    op.drop_index("ix_nc_approvals_execution", table_name="nc_approvals")
    op.drop_index("ix_nc_approvals_approval_id", table_name="nc_approvals")
    op.drop_table("nc_approvals")

    op.drop_index("ix_nc_policies_policy_version", table_name="nc_policies")
    op.drop_index("ix_nc_policies_policy_id", table_name="nc_policies")
    op.drop_table("nc_policies")

    op.drop_index("ix_nc_principals_namespace", table_name="nc_principals")
    op.drop_index("ix_nc_principals_principal_id", table_name="nc_principals")
    op.drop_table("nc_principals")

    op.drop_index(
        "ix_nc_resource_snapshots_dedup_key", table_name="nc_resource_snapshots"
    )
    op.drop_index(
        "ix_nc_resource_snapshots_resource_time", table_name="nc_resource_snapshots"
    )
    op.drop_table("nc_resource_snapshots")

    op.drop_index(
        "ix_nc_resource_relations_target", table_name="nc_resource_relations"
    )
    op.drop_index(
        "ix_nc_resource_relations_source", table_name="nc_resource_relations"
    )
    op.drop_index(
        "ix_nc_resource_relations_source_target_type", table_name="nc_resource_relations"
    )
    op.drop_table("nc_resource_relations")

    op.drop_index(
        "ix_nc_resource_aliases_resource", table_name="nc_resource_aliases"
    )
    op.drop_index(
        "ix_nc_resource_aliases_alias_uri", table_name="nc_resource_aliases"
    )
    op.drop_table("nc_resource_aliases")

    op.drop_index("ix_nc_resources_owner", table_name="nc_resources")
    op.drop_index(
        "ix_nc_resources_connector_instance", table_name="nc_resources"
    )
    op.drop_index("ix_nc_resources_namespace_sync", table_name="nc_resources")
    op.drop_index("ix_nc_resources_provider_resource", table_name="nc_resources")
    op.drop_index("ix_nc_resources_uri", table_name="nc_resources")
    op.drop_index("ix_nc_resources_resource_id", table_name="nc_resources")
    op.drop_table("nc_resources")

    op.drop_index(
        "ix_nc_connector_instances_provider", table_name="nc_connector_instances"
    )
    op.drop_index(
        "ix_nc_connector_instances_instance_id", table_name="nc_connector_instances"
    )
    op.drop_table("nc_connector_instances")
