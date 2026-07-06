"""Add optimistic-concurrency version column to tasks and meetings.

Uses SQLAlchemy's native version_id_col support (see app/models/task.py,
app/models/meeting.py) - every ORM UPDATE for these two models now includes
`AND version = <loaded value>` and raises StaleDataError on a stale write,
instead of silently last-write-wins overwriting a concurrent change.

Revision ID: 20260702_15
Revises: 20260702_14
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_15"
down_revision = "20260702_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("meetings", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("meetings", "version")
    op.drop_column("tasks", "version")
