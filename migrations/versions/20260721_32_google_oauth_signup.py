"""Add users.google_sub and users.auth_provider to support Google
Sign-In alongside the existing password login, for the new public
self-serve free-trial signup flow.

Revision ID: 20260721_32
Revises: 20260719_31
Create Date: 2026-07-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260721_32"
down_revision = "20260719_31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="password"),
    )
    op.add_column(
        "users",
        sa.Column("google_sub", sa.String(255), nullable=True),
    )
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "auth_provider")
