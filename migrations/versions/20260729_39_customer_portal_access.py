"""Add customer_portal_access table - durable, revocable, hashed tokens
granting external customers access to a self-serve document portal.

Revision ID: 20260729_39
Revises: 20260728_38
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260729_39"
down_revision = "20260728_38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_portal_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_portal_access_customer_id", "customer_portal_access", ["customer_id"])
    op.create_index("ix_customer_portal_access_token_hash", "customer_portal_access", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_customer_portal_access_token_hash", table_name="customer_portal_access")
    op.drop_index("ix_customer_portal_access_customer_id", table_name="customer_portal_access")
    op.drop_table("customer_portal_access")
