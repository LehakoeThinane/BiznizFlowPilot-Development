"""Add workflow definition index for dispatch lookup ordering.

Revision ID: 20260420_05
Revises: 20260420_04
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_05"
down_revision = "20260420_04"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    """Create composite index used by DatabaseDefinitionProvider query path."""
    index_name = "ix_workflow_definitions_business_event_active_created"
    if not _table_exists("workflow_definitions"):
        return
    if _index_exists("workflow_definitions", index_name):
        return

    op.create_index(
        index_name,
        "workflow_definitions",
        ["business_id", "event_type", "is_active", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop dispatch lookup composite index."""
    index_name = "ix_workflow_definitions_business_event_active_created"
    if not _table_exists("workflow_definitions"):
        return
    if not _index_exists("workflow_definitions", index_name):
        return

    op.drop_index(index_name, table_name="workflow_definitions")
