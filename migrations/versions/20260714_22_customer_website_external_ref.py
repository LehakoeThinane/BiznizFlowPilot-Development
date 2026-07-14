"""Add website and external_ref to customers - for lead-gen automation.

external_ref stores a provider-tagged dedup key (e.g. "google_places:<id>")
so a repeated lead-gen search doesn't create duplicate customers/leads for
the same prospect. Nullable - manually-created customers never set it.

Revision ID: 20260714_22
Revises: 20260713_21
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260714_22"
down_revision = "20260713_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("website", sa.String(500), nullable=True))
    op.add_column("customers", sa.Column("external_ref", sa.String(255), nullable=True))
    op.create_index(
        "uq_customers_business_external_ref",
        "customers",
        ["business_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_customers_business_external_ref", table_name="customers")
    op.drop_column("customers", "external_ref")
    op.drop_column("customers", "website")
