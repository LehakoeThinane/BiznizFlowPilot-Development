"""Tighten organization_id to NOT NULL/FK; relax businesses.email to per-org uniqueness.

Phase 3 of 3. Only safe to run after 20260702_03's backfill has left zero
businesses.organization_id NULLs (verify with:
  SELECT count(*) FROM businesses WHERE organization_id IS NULL;
before deploying this migration).

Two subsidiaries of different Organizations may legitimately share a
contact email; two subsidiaries of the *same* Organization must not -
hence composite (organization_id, email) uniqueness replacing the old
global-unique constraint.

Revision ID: 20260702_04
Revises: 20260702_03
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_04"
down_revision = "20260702_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("businesses", "organization_id", existing_type=sa.UUID(), nullable=False)
    op.create_foreign_key(
        "fk_businesses_organization",
        "businesses",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("businesses_email_key", "businesses", type_="unique")
    op.create_unique_constraint(
        "uq_businesses_organization_email", "businesses", ["organization_id", "email"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_businesses_organization_email", "businesses", type_="unique")
    op.create_unique_constraint("businesses_email_key", "businesses", ["email"])

    op.drop_constraint("fk_businesses_organization", "businesses", type_="foreignkey")
    op.alter_column("businesses", "organization_id", existing_type=sa.UUID(), nullable=True)
