"""Incidents + agents tables for the round-3 write routes (IN-1 / AG-3).

The web audit flagged two missing write paths:

- ``IN-1`` — no incident create/resolve/close routes. This revision adds the
  ``incidents`` table backing ``POST /api/incidents`` and the
  ``/resolve`` / ``/close`` transition routes.
- ``AG-3`` — no agent create route. This revision adds the ``agents`` table
  backing ``POST /api/agents`` (agent *instances*; the 14 native agent
  *types* remain owned by the in-memory ``AgentRegistry``).

Conventions match :mod:`001_initial` / :mod:`002_auth`: identifier columns
are ``sa.String()`` (the ORM's ``UUID(as_uuid=False)`` maps cleanly onto
them), JSONB columns use ``postgresql.JSONB(astext_type=sa.Text())`` so the
migration stays portable to the SQLite scratch databases used by the test
suite, and indexes follow the ``ix_<table>_<column>`` naming.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004_incidents_agents"
down_revision = "003_tasks_dependencies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("impact", sa.String(), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"], unique=False)
    op.create_index(
        "ix_incidents_status_severity", "incidents", ["status", "severity"], unique=False
    )

    # agents (agent instances created through POST /api/agents)
    op.create_table(
        "agents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v0"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("prompt_template", sa.String(), nullable=True),
        sa.Column(
            "tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
    op.create_index("ix_agents_status", "agents", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agents_status", table_name="agents")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_incidents_status_severity", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_table("incidents")
