"""Extend event_type_enum with Organization/Subsidiary/Invitation/Impersonation event types.

Revision ID: 20260702_08
Revises: 20260702_07
Create Date: 2026-07-02
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260702_08"
down_revision = "20260702_07"
branch_labels = None
depends_on = None

NEW_VALUES = [
    "organization_provisioned",
    "organization_updated",
    "subsidiary_created",
    "subsidiary_updated",
    "subsidiary_deactivated",
    "user_invited",
    "user_invite_accepted",
    "user_invite_revoked",
    "impersonation_session_started",
    "impersonation_session_ended",
]


def upgrade() -> None:
    """Add new enum values to event_type_enum.

    PostgreSQL enums are extended with ALTER TYPE ... ADD VALUE.
    Each value is added idempotently (IF NOT EXISTS).
    """
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade is a no-op.

    PostgreSQL does not support removing values from an existing enum type.
    The extra values are harmless if unused.
    """
    pass
