"""Add trial_reminder_sent_at to organizations for idempotent trial reminders.

The trial-expiry reminder Celery task must send exactly one reminder email
per org, regardless of how many times it runs during the reminder window -
this nullable timestamp is the idempotency marker (NULL = not yet sent).

Revision ID: 20260710_19
Revises: 20260706_18
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260710_19"
down_revision = "20260706_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("trial_reminder_sent_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("organizations", "trial_reminder_sent_at")
