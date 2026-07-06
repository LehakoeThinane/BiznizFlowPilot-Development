"""Add source_workflow_action_id to tasks for create_task idempotency.

Gives CreateTaskHandler (app/workflow_engine/handlers/create_task.py) a real
uniqueness guarantee: if the same workflow action is retried after an
ambiguous outcome, the second INSERT collides on this constraint instead of
silently creating a duplicate task.

Revision ID: 20260706_16
Revises: 20260702_15
Create Date: 2026-07-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260706_16"
down_revision = "20260702_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("source_workflow_action_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_tasks_source_workflow_action_id",
        "tasks",
        ["source_workflow_action_id"],
    )
    op.create_unique_constraint(
        "uq_tasks_source_workflow_action_id",
        "tasks",
        ["source_workflow_action_id"],
    )
    op.create_foreign_key(
        "fk_tasks_source_workflow_action_id",
        "tasks",
        "workflow_actions",
        ["source_workflow_action_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_source_workflow_action_id", "tasks", type_="foreignkey")
    op.drop_constraint("uq_tasks_source_workflow_action_id", "tasks", type_="unique")
    op.drop_index("ix_tasks_source_workflow_action_id", table_name="tasks")
    op.drop_column("tasks", "source_workflow_action_id")
