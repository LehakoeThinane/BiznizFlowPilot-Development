"""Extend notification_type with 'onboarding' - used to sync HR and IT Admin
around invite/employee onboarding activity (invite sent/accepted, employee
added without a linked login, etc).

Revision ID: 20260805_43
Revises: 20260803_42
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260805_43"
down_revision = "20260803_42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'onboarding'")


def downgrade() -> None:
    # Postgres cannot remove an enum value; 'onboarding' is left in notification_type on downgrade.
    pass
