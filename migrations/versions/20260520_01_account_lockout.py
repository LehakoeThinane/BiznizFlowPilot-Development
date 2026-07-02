"""Add account lockout columns to users table.

Revision ID: 20260520_01
Revises: 20260504_01
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "20260520_01"
down_revision = "20260504_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_users_locked_until", "users", ["locked_until"])


def downgrade() -> None:
    op.drop_index("ix_users_locked_until", table_name="users")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
