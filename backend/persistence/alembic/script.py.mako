"""Alembic script template for NerveCenter.

This is the template used by ``alembic revision`` to generate new migration
files. It includes the standard boilderplate plus a few helpful notes for
NerveCenter-specific conventions:

- Use ``batch_alter_table`` for columns that need ALTER TABLE (SQLite compatibility).
- Vector columns are created with ``postgresql_using="gist"`` for pgvector.
- Timestamp columns use ``server_default=func.now()`` for automatic timestamps.
- Foreign keys reference other tables by their plural snake_case name.
"""

from typing import Any, List

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
${upgrades if upgrades else "    pass"}


def downgrade() -> None:
${downgrades if downgrades else "    pass"}
