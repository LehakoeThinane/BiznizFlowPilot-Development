"""Add CHECK constraints on users.role and platform_admins.platform_role.

Both columns were plain, unconstrained strings - every RBAC check in the
app is a Python string comparison with no schema-level backstop, so a bug
or a direct DB write could leave a row with a role matching none of the
app's checks. Data audited against the current database before this
migration was written: users.role only contained 'owner'/'manager',
platform_admins.platform_role only contained 'super_admin' - no existing
rows violate the constraints being added here. If this ever fails in
another environment, find and fix the offending rows before retrying:
    SELECT id, role FROM users WHERE role NOT IN ('owner','manager','staff','it_admin');
    SELECT id, platform_role FROM platform_admins WHERE platform_role NOT IN ('support','billing_ops','admin','super_admin');

Revision ID: 20260706_17
Revises: 20260706_16
Create Date: 2026-07-06
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260706_17"
down_revision = "20260706_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('owner', 'manager', 'staff', 'it_admin')",
    )
    op.create_check_constraint(
        "ck_platform_admins_platform_role_valid",
        "platform_admins",
        "platform_role IN ('support', 'billing_ops', 'admin', 'super_admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_platform_admins_platform_role_valid", "platform_admins", type_="check")
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
