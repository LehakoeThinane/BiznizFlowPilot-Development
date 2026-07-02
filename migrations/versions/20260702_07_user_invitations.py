"""Add user_invitations table - domain-restricted employee onboarding.

Revision ID: 20260702_07
Revises: 20260702_06
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_07"
down_revision = "20260702_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'staff'")),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_invitations_token_hash"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked', 'expired')",
            name="ck_user_invitations_status_valid",
        ),
    )
    op.create_index(op.f("ix_user_invitations_business_id"), "user_invitations", ["business_id"], unique=False)
    op.create_index(op.f("ix_user_invitations_organization_id"), "user_invitations", ["organization_id"], unique=False)
    op.create_index(op.f("ix_user_invitations_email"), "user_invitations", ["email"], unique=False)
    op.create_index(
        "uq_user_invitations_pending_business_email",
        "user_invitations",
        ["business_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_invitations_pending_business_email", table_name="user_invitations")
    op.drop_index(op.f("ix_user_invitations_email"), table_name="user_invitations")
    op.drop_index(op.f("ix_user_invitations_organization_id"), table_name="user_invitations")
    op.drop_index(op.f("ix_user_invitations_business_id"), table_name="user_invitations")
    op.drop_table("user_invitations")
