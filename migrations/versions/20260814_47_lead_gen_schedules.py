"""Add lead_gen_schedules table - saved Google Places searches the scheduled
lead-gen task (Mon/Wed/Thu) re-runs automatically instead of requiring a
human to trigger POST /api/v1/leads/find by hand each time.

Revision ID: 20260814_47
Revises: 20260806_46
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260814_47"
down_revision = "20260806_46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_gen_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_gen_schedules_business_id", "lead_gen_schedules", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_gen_schedules_business_id", "lead_gen_schedules")
    op.drop_table("lead_gen_schedules")
