"""Add soft-delete column to workflow definitions.

Revision ID: 20260420_06
Revises: 20260420_05
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_06"
down_revision = "20260420_05"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    """Add soft-delete support to workflow definitions."""
    table_name = "workflow_definitions"
    column_name = "deleted_at"
    index_name = "ix_workflow_definitions_deleted_at"

    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, column_name):
        op.add_column(
            table_name,
            sa.Column(column_name, sa.DateTime(timezone=True), nullable=True),
        )

    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, [column_name], unique=False)


def downgrade() -> None:
    """Remove soft-delete support from workflow definitions."""
    table_name = "workflow_definitions"
    column_name = "deleted_at"
    index_name = "ix_workflow_definitions_deleted_at"

    if not _table_exists(table_name):
        return

    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)

    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)
