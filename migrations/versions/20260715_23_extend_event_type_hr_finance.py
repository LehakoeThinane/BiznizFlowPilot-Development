"""Extend event_type_enum with Supplier/HR/Finance/User-profile event types.

These EventType members existed in app/core/enums.py but were never added to
the production Postgres enum, causing InvalidTextRepresentation errors (500s)
on every action that emits one of them - e.g. creating an employee.

Revision ID: 20260715_23
Revises: 20260714_22
Create Date: 2026-07-15
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260715_23"
down_revision = "20260714_22"
branch_labels = None
depends_on = None

NEW_VALUES = [
    "supplier_created",
    "supplier_updated",
    "supplier_deleted",
    "employee_created",
    "employee_updated",
    "employee_deactivated",
    "leave_requested",
    "leave_status_changed",
    "payroll_generated",
    "payroll_approved",
    "expense_created",
    "expense_updated",
    "expense_deleted",
    "invoice_created",
    "invoice_status_changed",
    "invoice_sent",
    "invoice_deleted",
    "user_profile_updated",
    "user_password_changed",
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
