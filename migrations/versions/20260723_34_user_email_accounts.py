"""Add user_email_accounts table - each employee can self-service connect
their own personal mailbox (IMAP for reading, SMTP for sending), separate
from the org-wide SMTP sender added in 20260722_33.

Revision ID: 20260723_34
Revises: 20260722_33
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260723_34"
down_revision = "20260722_33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_email_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("imap_host", sa.String(255), nullable=True),
        sa.Column("imap_port", sa.Integer(), nullable=True),
        sa.Column("imap_username", sa.String(255), nullable=True),
        sa.Column("imap_password_encrypted", sa.String(500), nullable=True),
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        sa.Column("smtp_password_encrypted", sa.String(500), nullable=True),
        sa.Column("smtp_from_email", sa.String(255), nullable=True),
        sa.Column("smtp_from_name", sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_email_accounts_user_id"),
    )
    op.create_index("ix_user_email_accounts_business", "user_email_accounts", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_user_email_accounts_business", table_name="user_email_accounts")
    op.drop_table("user_email_accounts")
