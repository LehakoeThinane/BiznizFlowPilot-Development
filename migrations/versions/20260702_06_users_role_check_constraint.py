"""Add it_admin to users.role and add the column's first-ever DB-level CHECK constraint.

Safe against existing data: only owner|manager|staff exist today. As a
side effect this permanently forecloses a "superadmin"-style value ever
landing in this column again - platform-wide authority must never share
the same column that gates tenant permissions (see app/api/admin.py's
now-replaced "superadmin" scaffold, which relied on exactly that column
without any DB-level constraint at all).

Revision ID: 20260702_06
Revises: 20260702_05
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260702_06"
down_revision = "20260702_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('owner', 'manager', 'staff', 'it_admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
