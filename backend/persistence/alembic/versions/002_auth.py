"""Auth infrastructure (spec sso-integration, S101).

Creates the four tables backing the signed-JWT auth surface:

- ``auth_sessions``       — one row per issued NerveCenter token (access /
                            refresh / device).  The PK doubles as the JWT
                            ``jti``; persisting sessions means an API restart
                            never invalidates a still-valid JWT, and logout
                            revokes by flipping ``revoked``.
- ``auth_devices``        — paired devices (prompot §71).  ``device_id`` is
                            the stable identifier chosen by the device.
- ``pairing_challenges``  — short-lived (≤5 min) device pairing challenges
                            (prompot §71).
- ``approvals``           — device-bound approvals (prompot §72) bound to
                            ``device_id`` + ``nonce`` + ``expires_at`` and an
                            exact ``planned_change_id``; ``change_fingerprint``
                            is the SHA-256 of the bound change's content at
                            approval time.

Conventions match :mod:`001_initial`: all identifier columns are
``sa.String()`` (the ORM's ``UUID(as_uuid=False)`` maps cleanly onto them),
server defaults and redundant PK indexes are omitted, and indexes follow the
``ix_<table>_<column>`` naming.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_auth"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # auth_sessions
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("sub", sa.String(length=255), nullable=False),
        sa.Column("typ", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_id", "auth_sessions", ["id"], unique=False)
    op.create_index("ix_auth_sessions_sub", "auth_sessions", ["sub"], unique=False)
    op.create_index("ix_auth_sessions_typ", "auth_sessions", ["typ"], unique=False)
    op.create_index(
        "ix_auth_sessions_sub_expires_at",
        "auth_sessions",
        ["sub", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_sessions_device_id", "auth_sessions", ["device_id"], unique=False
    )

    # auth_devices
    op.create_table(
        "auth_devices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "attestation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("ix_auth_devices_id", "auth_devices", ["id"], unique=False)
    op.create_index(
        "ix_auth_devices_device_id", "auth_devices", ["device_id"], unique=True
    )

    # pairing_challenges
    op.create_table(
        "pairing_challenges",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("challenge_id", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
    )
    op.create_index("ix_pairing_challenges_id", "pairing_challenges", ["id"], unique=False)
    op.create_index(
        "ix_pairing_challenges_challenge_id",
        "pairing_challenges",
        ["challenge_id"],
        unique=True,
    )
    op.create_index(
        "ix_pairing_challenges_nonce", "pairing_challenges", ["nonce"], unique=False
    )
    op.create_index(
        "ix_pairing_challenges_status_expires_at",
        "pairing_challenges",
        ["status", "expires_at"],
        unique=False,
    )

    # approvals
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("planned_change_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("approver_sub", sa.String(length=255), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("invalidation_reason", sa.String(length=255), nullable=True),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_id", "approvals", ["id"], unique=False)
    op.create_index(
        "ix_approvals_planned_change_id",
        "approvals",
        ["planned_change_id"],
        unique=False,
    )
    op.create_index("ix_approvals_device_id", "approvals", ["device_id"], unique=False)
    op.create_index(
        "ix_approvals_decision_expires_at",
        "approvals",
        ["decision", "expires_at"],
        unique=False,
    )
    # Bind approvals to the exact planned change (§72).  ``planned_changes.id``
    # is a String PK in 001_initial, so no cast is required.
    op.create_foreign_key(
        "approvals_fk_planned_change_id_planned_changes",
        source_table="approvals",
        local_cols=["planned_change_id"],
        referent_table="planned_changes",
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Reverse the create order, dropping the FK first.
    op.drop_constraint(
        "approvals_fk_planned_change_id_planned_changes",
        "approvals",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_approvals_decision_expires_at", table_name="approvals"
    )
    op.drop_index("ix_approvals_device_id", table_name="approvals")
    op.drop_index("ix_approvals_planned_change_id", table_name="approvals")
    op.drop_index("ix_approvals_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index(
        "ix_pairing_challenges_status_expires_at", table_name="pairing_challenges"
    )
    op.drop_index("ix_pairing_challenges_nonce", table_name="pairing_challenges")
    op.drop_index(
        "ix_pairing_challenges_challenge_id", table_name="pairing_challenges"
    )
    op.drop_index("ix_pairing_challenges_id", table_name="pairing_challenges")
    op.drop_table("pairing_challenges")

    op.drop_index("ix_auth_devices_device_id", table_name="auth_devices")
    op.drop_index("ix_auth_devices_id", table_name="auth_devices")
    op.drop_table("auth_devices")

    op.drop_index(
        "ix_auth_sessions_device_id", table_name="auth_sessions"
    )
    op.drop_index(
        "ix_auth_sessions_sub_expires_at", table_name="auth_sessions"
    )
    op.drop_index("ix_auth_sessions_typ", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_sub", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
