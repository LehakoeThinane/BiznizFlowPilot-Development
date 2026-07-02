"""Add platform_admins and platform_audit_log tables - vendor-side identity, fully
separate from tenant `users` (never joined, never shares the users.role column).

Revision ID: 20260702_09
Revises: 20260702_08
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260702_09"
down_revision = "20260702_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("platform_role", sa.String(length=20), nullable=False, server_default=sa.text("'support'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("impersonation_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
        sa.CheckConstraint(
            "platform_role IN ('support', 'billing_ops', 'admin', 'super_admin')",
            name="ck_platform_admins_role_valid",
        ),
    )
    op.create_index(op.f("ix_platform_admins_email"), "platform_admins", ["email"], unique=False)

    op.create_table(
        "platform_audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("platform_admin_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False, server_default=sa.text("'success'")),
        sa.Column("meta_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["platform_admin_id"], ["platform_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "result IN ('success', 'failed', 'denied')",
            name="ck_platform_audit_log_result_valid",
        ),
    )
    op.create_index(op.f("ix_platform_audit_log_platform_admin_id"), "platform_audit_log", ["platform_admin_id"], unique=False)
    op.create_index(op.f("ix_platform_audit_log_action"), "platform_audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_platform_audit_log_created_at"), "platform_audit_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_audit_log_created_at"), table_name="platform_audit_log")
    op.drop_index(op.f("ix_platform_audit_log_action"), table_name="platform_audit_log")
    op.drop_index(op.f("ix_platform_audit_log_platform_admin_id"), table_name="platform_audit_log")
    op.drop_table("platform_audit_log")
    op.drop_index(op.f("ix_platform_admins_email"), table_name="platform_admins")
    op.drop_table("platform_admins")
