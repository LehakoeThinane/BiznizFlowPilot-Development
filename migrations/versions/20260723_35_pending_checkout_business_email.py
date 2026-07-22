"""Add business_email to pending_checkouts - distinct from owner_email
(billing/payment contact) so the two can differ: owner_email may be a
personal address used only for PayFast billing, while business_email is the
custom-domain address actually used for the owner's platform registration
invite and the org's authorized-domain derivation.

Revision ID: 20260723_35
Revises: 20260723_34
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260723_35"
down_revision = "20260723_34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pending_checkouts", sa.Column("business_email", sa.String(255), nullable=False))


def downgrade() -> None:
    op.drop_column("pending_checkouts", "business_email")
