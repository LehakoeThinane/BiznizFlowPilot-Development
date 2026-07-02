"""Make workflow timestamp columns timezone-aware.

Revision ID: 20260420_03
Revises: 20260420_02
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_03"
down_revision = "20260420_02"
branch_labels = None
depends_on = None


WORKFLOW_TABLES = ("workflows", "workflow_actions", "workflow_runs")
TIMESTAMP_COLUMNS = ("created_at", "updated_at")


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    """Convert workflow timestamps to timezone-aware columns."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    for table_name in WORKFLOW_TABLES:
        if not _table_exists(table_name):
            continue

        for column_name in TIMESTAMP_COLUMNS:
            alter_kwargs = {
                "table_name": table_name,
                "column_name": column_name,
                "existing_type": sa.DateTime(timezone=False),
                "type_": sa.DateTime(timezone=True),
                "existing_nullable": False,
            }
            if is_postgres:
                alter_kwargs["postgresql_using"] = f"{column_name} AT TIME ZONE 'UTC'"

            op.alter_column(**alter_kwargs)


def downgrade() -> None:
    """Revert workflow timestamps back to naive datetime columns."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    for table_name in WORKFLOW_TABLES:
        if not _table_exists(table_name):
            continue

        for column_name in TIMESTAMP_COLUMNS:
            alter_kwargs = {
                "table_name": table_name,
                "column_name": column_name,
                "existing_type": sa.DateTime(timezone=True),
                "type_": sa.DateTime(timezone=False),
                "existing_nullable": False,
            }
            if is_postgres:
                alter_kwargs["postgresql_using"] = f"{column_name} AT TIME ZONE 'UTC'"

            op.alter_column(**alter_kwargs)
