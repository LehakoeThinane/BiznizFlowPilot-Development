"""Replace organizations.primary_domain/domain_verified with organization_domains table.

Done before any invite-domain-validation logic is written against the
single-domain columns (per architecture review: real organizations can
legitimately own more than one domain). Safe to drop the placeholder
columns outright - no organization has set a domain yet (both columns
are still NULL/false for every row from the Phase 1 backfill).

Revision ID: 20260702_05
Revises: 20260702_04
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_05"
down_revision = "20260702_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("organizations", "domain_verified")
    op.drop_column("organizations", "primary_domain")

    op.create_table(
        "organization_domains",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain", name="uq_organization_domains_domain"),
    )
    op.create_index(
        op.f("ix_organization_domains_organization_id"),
        "organization_domains",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_organization_domains_one_primary",
        "organization_domains",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index("uq_organization_domains_one_primary", table_name="organization_domains")
    op.drop_index(op.f("ix_organization_domains_organization_id"), table_name="organization_domains")
    op.drop_table("organization_domains")

    op.add_column("organizations", sa.Column("primary_domain", sa.String(length=255), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("domain_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_unique_constraint(
        "uq_organizations_primary_domain", "organizations", ["primary_domain"]
    )
