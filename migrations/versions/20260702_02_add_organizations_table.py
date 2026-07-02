"""Add organizations table and nullable subsidiary-linkage columns on businesses.

Phase 1 of 3 for the Organization/subsidiary rollout (see 20260702_03 for the
backfill, 20260702_04 for tightening constraints). This migration is purely
additive and changes no existing behavior — safe to deploy standalone.

Revision ID: 20260702_02
Revises: 20260702_01
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_02"
down_revision = "20260702_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("primary_domain", sa.String(length=255), nullable=True),
        sa.Column("domain_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("billing_email", sa.String(length=255), nullable=False),
        sa.Column("plan_tier", sa.String(length=50), nullable=False, server_default=sa.text("'legacy'")),
        sa.Column("billing_mode", sa.String(length=20), nullable=False, server_default=sa.text("'organization'")),
        sa.Column("subscription_status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seats_included", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("primary_domain", name="uq_organizations_primary_domain"),
    )
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)

    op.add_column("businesses", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.add_column(
        "businesses",
        sa.Column("is_primary_subsidiary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "businesses",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "businesses",
        sa.Column("billed_independently", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("businesses", sa.Column("seat_limit", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_businesses_organization_id"), "businesses", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_businesses_organization_id"), table_name="businesses")
    op.drop_column("businesses", "seat_limit")
    op.drop_column("businesses", "billed_independently")
    op.drop_column("businesses", "is_active")
    op.drop_column("businesses", "is_primary_subsidiary")
    op.drop_column("businesses", "organization_id")

    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_table("organizations")
