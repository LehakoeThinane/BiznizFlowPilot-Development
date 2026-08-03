"""Extend event_type_enum with payslip_adjusted.

Revision ID: 20260803_41
Revises: 20260803_40
Create Date: 2026-08-03
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260803_41"
down_revision = "20260803_40"
branch_labels = None
depends_on = None

NEW_VALUES = [
    "payslip_adjusted",
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
