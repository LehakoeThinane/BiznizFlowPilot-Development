"""Add workflow run/action timing columns for observability.

Revision ID: 20260421_01
Revises: 20260420_06
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260421_01"
down_revision = "20260420_06"
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


def _add_timing_columns_and_indexes(
    table_name: str,
    indexes: Sequence[tuple[str, str]],
) -> None:
    started_col = "started_at"
    finished_col = "finished_at"

    if not _column_exists(table_name, started_col):
        op.add_column(
            table_name,
            sa.Column(started_col, sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists(table_name, finished_col):
        op.add_column(
            table_name,
            sa.Column(finished_col, sa.DateTime(timezone=True), nullable=True),
        )

    for index_name, column_name in indexes:
        if not _index_exists(table_name, index_name):
            op.create_index(index_name, table_name, [column_name], unique=False)


def _drop_timing_columns_and_indexes(
    table_name: str,
    indexes: Sequence[tuple[str, str]],
) -> None:
    started_col = "started_at"
    finished_col = "finished_at"

    for index_name, _column_name in indexes:
        if _index_exists(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)

    if _column_exists(table_name, finished_col):
        op.drop_column(table_name, finished_col)
    if _column_exists(table_name, started_col):
        op.drop_column(table_name, started_col)


def upgrade() -> None:
    """Add run/action timing columns and indexes."""
    run_table = "workflow_runs"
    action_table = "workflow_actions"

    run_indexes = [
        ("ix_workflow_runs_started_at", "started_at"),
        ("ix_workflow_runs_finished_at", "finished_at"),
    ]
    action_indexes = [
        ("ix_workflow_actions_started_at", "started_at"),
        ("ix_workflow_actions_finished_at", "finished_at"),
    ]

    if _table_exists(run_table):
        _add_timing_columns_and_indexes(run_table, run_indexes)
    if _table_exists(action_table):
        _add_timing_columns_and_indexes(action_table, action_indexes)


def downgrade() -> None:
    """Remove run/action timing columns and indexes."""
    run_table = "workflow_runs"
    action_table = "workflow_actions"

    run_indexes = [
        ("ix_workflow_runs_started_at", "started_at"),
        ("ix_workflow_runs_finished_at", "finished_at"),
    ]
    action_indexes = [
        ("ix_workflow_actions_started_at", "started_at"),
        ("ix_workflow_actions_finished_at", "finished_at"),
    ]

    if _table_exists(action_table):
        _drop_timing_columns_and_indexes(action_table, action_indexes)
    if _table_exists(run_table):
        _drop_timing_columns_and_indexes(run_table, run_indexes)
