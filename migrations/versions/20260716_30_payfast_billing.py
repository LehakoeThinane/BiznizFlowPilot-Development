"""Replace Stripe billing with PayFast: add pending_checkouts table, swap
organizations.stripe_customer_id for organizations.payfast_token.

Revision ID: 20260716_30
Revises: 20260716_29
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260716_30"
down_revision = "20260716_29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_checkouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("org_name", sa.String(length=255), nullable=False),
        sa.Column("subsidiary_name", sa.String(length=255), nullable=True),
        sa.Column("owner_email", sa.String(length=255), nullable=False),
        sa.Column("plan_tier", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.CheckConstraint("status IN ('pending', 'completed')", name="ck_pending_checkouts_status"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
    op.drop_column("organizations", "stripe_customer_id")
    op.add_column("organizations", sa.Column("payfast_token", sa.String(length=255), nullable=True))
    op.create_index("ix_organizations_payfast_token", "organizations", ["payfast_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organizations_payfast_token", table_name="organizations")
    op.drop_column("organizations", "payfast_token")
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.create_index("ix_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"], unique=True)

    op.drop_table("pending_checkouts")
