"""Add task_assignees table for multi-person task assignment.

`assigned_to` on tasks remains the single "primary" assignee used by
existing staff-visibility/filtering logic; this table holds the full
assignee set (primary included) for tasks that need more than one person.

Revision ID: 20260715_24
Revises: 20260715_23
Create Date: 2026-07-15
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260715_24"
down_revision = "20260715_23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_assignees_task_id", "task_assignees", ["task_id"])
    op.create_index("ix_task_assignees_user_id", "task_assignees", ["user_id"])
    op.create_index("ix_task_assignees_task_user", "task_assignees", ["task_id", "user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_task_assignees_task_user", table_name="task_assignees")
    op.drop_index("ix_task_assignees_user_id", table_name="task_assignees")
    op.drop_index("ix_task_assignees_task_id", table_name="task_assignees")
    op.drop_table("task_assignees")
