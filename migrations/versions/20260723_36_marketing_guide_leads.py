"""Add marketing_guide_leads table - top-of-funnel sales leads captured
when an anonymous marketing-site visitor downloads a gated guide.

Revision ID: 20260723_36
Revises: 20260723_35
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260723_36"
down_revision = "20260723_35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_guide_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("guide_slug", sa.String(length=100), nullable=False),
        sa.Column("source_page", sa.String(length=255), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketing_guide_leads_email", "marketing_guide_leads", ["email"])


def downgrade() -> None:
    op.drop_index("ix_marketing_guide_leads_email", table_name="marketing_guide_leads")
    op.drop_table("marketing_guide_leads")
