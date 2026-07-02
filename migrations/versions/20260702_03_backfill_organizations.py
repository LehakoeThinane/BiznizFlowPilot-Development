"""Backfill one Organization per existing Business row.

Phase 2 of 3. Every pre-existing Business gets its own Organization
(primary_domain = NULL, so no existing customer's invite flow becomes
domain-restricted as a side effect of this migration; restriction is
opt-in only, set later by an IT Admin). Must ship in the same deploy as
the updated AuthService.register() (20260702_03 code changes), so new
signups also get an Organization and organization_id never goes NULL
again after this point.

This migration relies on businesses.email still being globally unique
at this point in the sequence (the constraint is only dropped in
20260702_04, after this backfill completes) to safely join backfilled
organizations back to their business by billing_email = business.email.

Revision ID: 20260702_03
Revises: 20260702_02
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260702_03"
down_revision = "20260702_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        text(
            """
            INSERT INTO organizations (
                id, created_at, updated_at, name, primary_domain, domain_verified,
                billing_email, plan_tier, billing_mode, subscription_status
            )
            SELECT
                gen_random_uuid(), now(), now(), b.name, NULL, false,
                b.email, 'legacy', 'organization', 'active'
            FROM businesses b
            WHERE b.organization_id IS NULL
            """
        )
    )

    bind.execute(
        text(
            """
            UPDATE businesses b
            SET organization_id = o.id,
                is_primary_subsidiary = true
            FROM organizations o
            WHERE o.billing_email = b.email
              AND b.organization_id IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("UPDATE businesses SET organization_id = NULL, is_primary_subsidiary = false"))
    bind.execute(text("DELETE FROM organizations"))
