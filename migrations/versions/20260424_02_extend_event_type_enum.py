"""Extend event_type_enum with CRM lifecycle and ERP event types.

Revision ID: 20260424_02
Revises: 20260424_01
Create Date: 2026-04-24
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260424_02"
down_revision = "20260424_01"
branch_labels = None
depends_on = None

# New event type values added for auto-event generation and ERP modules.
NEW_VALUES = [
    # CRM lifecycle events
    "lead_updated",
    "lead_assigned",
    "lead_deleted",
    "task_updated",
    "task_deleted",
    "customer_created",
    "customer_updated",
    "customer_deleted",
    # ERP events
    "product_created",
    "product_updated",
    "product_deleted",
    "order_created",
    "order_confirmed",
    "order_shipped",
    "order_delivered",
    "order_cancelled",
    "stock_low",
    "stock_adjusted",
    "stock_transferred",
    "purchase_order_created",
    "purchase_order_sent",
    "purchase_order_received",
    # Existing values added later (may already exist)
    "lead_idle",
    "task_overdue",
]


def upgrade() -> None:
    """Add new enum values to event_type_enum.
    
    PostgreSQL enums are extended with ALTER TYPE ... ADD VALUE.
    Each value is added idempotently (IF NOT EXISTS).
    """
    for value in NEW_VALUES:
        op.execute(
            f"ALTER TYPE event_type_enum ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    """Downgrade is a no-op.
    
    PostgreSQL does not support removing values from an existing enum type.
    The extra values are harmless if unused.
    """
    pass
