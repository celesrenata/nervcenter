"""Add the missing ``tasks.dependencies`` column (schema drift, audit-gaps U-5).

:mod:`001_initial` created the ``tasks`` table without its ``dependencies``
column even though the ORM model (``backend.persistence.models.tasks.Task.dependencies``)
declares it as a non-nullable JSONB attribute.  Any read of the whole table
(``SELECT tasks.dependencies ...``, e.g. ``GET /api/tasks`` via
``TaskService.list_tasks``) therefore fails with
``sqlalchemy.exc.ProgrammingError: column tasks.dependencies does not exist``
against databases that were built from this revision.

This revision closes the gap the way the project actually migrates: it is an
alembic revision on the existing ``001_initial -> 002_auth`` chain, applied by
``python -m backend.persistence.migrate upgrade head`` (the cluster migrate-job
entrypoint, ``deployments/kubernetes/base/migrate-job.yaml``).

Conventions match :mod:`001_initial` / :mod:`002_auth`: the column is
``postgresql.JSONB`` (the ORM's ``Jsonb`` alias is plain ``JSONB``), NOT NULL
with a Python-side ``default=list`` on the model.  The ``server_default`` is
the plain literal ``'[]'`` (not ``'[]'::jsonb``) so it renders valid DDL on
both PostgreSQL and SQLite scratch databases; the ORM always writes a JSON
array, so no cast ambiguity arises.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_tasks_dependencies"
down_revision = "002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table is a no-op rewrite on PostgreSQL (the server supports
    # ALTER TABLE ... ADD COLUMN natively) but keeps the migration portable
    # to SQLite for local dev / test scratch databases.
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "dependencies",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("dependencies")
