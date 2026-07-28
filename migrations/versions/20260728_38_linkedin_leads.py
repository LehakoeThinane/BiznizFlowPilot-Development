"""Add linkedin_leads table - top-of-funnel sales leads captured from
LinkedIn ads (native Lead Gen Form CSV import, our own landing page, or a
future automated API poll). Root-level, no business_id, same tier as
marketing_guide_leads.

Revision ID: 20260728_38
Revises: 20260727_37
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260728_38"
down_revision = "20260727_37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("linkedin_lead_id", sa.String(length=255), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=True),
        sa.Column("form_name", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("utm_source", sa.String(length=255), nullable=True),
        sa.Column("utm_medium", sa.String(length=255), nullable=True),
        sa.Column("utm_campaign", sa.String(length=255), nullable=True),
        sa.Column("ingestion_source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("assigned_to", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'disqualified')",
            name="ck_linkedin_leads_status",
        ),
        sa.CheckConstraint(
            "ingestion_source IN ('csv_import', 'api_poll', 'landing_page')",
            name="ck_linkedin_leads_ingestion_source",
        ),
    )
    op.create_index("ix_linkedin_leads_linkedin_lead_id", "linkedin_leads", ["linkedin_lead_id"], unique=True)
    op.create_index("ix_linkedin_leads_email", "linkedin_leads", ["email"])


def downgrade() -> None:
    op.drop_index("ix_linkedin_leads_email", table_name="linkedin_leads")
    op.drop_index("ix_linkedin_leads_linkedin_lead_id", table_name="linkedin_leads")
    op.drop_table("linkedin_leads")
