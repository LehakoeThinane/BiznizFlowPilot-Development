"""Add stripe_customer_id to organizations for self-serve signup idempotency.

Self-serve signups are provisioned automatically from a Stripe
checkout.session.completed webhook (see app/services/billing.py). Stripe
delivers webhooks at-least-once, so a redelivered event must not create a
second Organization for the same paying customer - the unique constraint on
this column is what a repeat delivery collides against.

Revision ID: 20260706_18
Revises: 20260706_17
Create Date: 2026-07-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260706_18"
down_revision = "20260706_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
    op.drop_column("organizations", "stripe_customer_id")
