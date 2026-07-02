"""Fix schema drift between models and database.

Adds columns/indexes the ORM models expect but the database never got:
- users.avatar_url (referenced by every user query -> broke login/register)
- missing business_id indexes on HR/finance/invoice/notification tables
- updated_at on order/purchase-order line items, created_at on stock_levels
- workflow_definitions.event_type promoted from VARCHAR to the native
  event_type_enum type already used by events.event_type

Revision ID: 20260702_01
Revises: 20260520_01
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260702_01"
down_revision = "20260520_01"
branch_labels = None
depends_on = None


event_type_enum = postgresql.ENUM(
    "lead_created", "lead_updated", "lead_status_changed", "lead_assigned",
    "lead_deleted", "lead_idle", "task_created", "task_updated", "task_assigned",
    "task_completed", "task_deleted", "task_overdue", "customer_created",
    "customer_updated", "customer_deleted", "product_created", "product_updated",
    "product_deleted", "supplier_created", "supplier_updated", "supplier_deleted",
    "order_created", "order_confirmed", "order_shipped", "order_delivered",
    "order_cancelled", "stock_low", "stock_adjusted", "stock_transferred",
    "purchase_order_created", "purchase_order_sent", "purchase_order_received",
    "employee_created", "employee_updated", "employee_deactivated",
    "leave_requested", "leave_status_changed", "payroll_generated",
    "payroll_approved", "expense_created", "expense_updated", "expense_deleted",
    "invoice_created", "invoice_status_changed", "invoice_sent", "invoice_deleted",
    "user_profile_updated", "user_password_changed", "workflow_triggered", "custom",
    name="event_type_enum",
    create_type=False,
)


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))

    op.create_index("ix_departments_business_id", "departments", ["business_id"], unique=False)
    op.create_index("ix_employees_business_id", "employees", ["business_id"], unique=False)
    op.create_index("ix_expenses_business_id", "expenses", ["business_id"], unique=False)
    op.create_index("ix_invoices_business_id", "invoices", ["business_id"], unique=False)
    op.create_index("ix_leave_requests_business_id", "leave_requests", ["business_id"], unique=False)
    op.create_index("ix_leave_types_business_id", "leave_types", ["business_id"], unique=False)
    op.create_index("ix_notifications_business_id", "notifications", ["business_id"], unique=False)
    op.create_index("ix_payroll_periods_business_id", "payroll_periods", ["business_id"], unique=False)
    op.create_index("ix_payslips_business_id", "payslips", ["business_id"], unique=False)

    op.add_column(
        "order_line_items",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "purchase_order_line_items",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "stock_levels",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.alter_column(
        "workflow_definitions",
        "event_type",
        existing_type=sa.VARCHAR(length=100),
        type_=event_type_enum,
        postgresql_using="event_type::event_type_enum",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "workflow_definitions",
        "event_type",
        existing_type=event_type_enum,
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
    )

    op.drop_column("stock_levels", "created_at")
    op.drop_column("purchase_order_line_items", "updated_at")
    op.drop_column("order_line_items", "updated_at")

    op.drop_index("ix_payslips_business_id", table_name="payslips")
    op.drop_index("ix_payroll_periods_business_id", table_name="payroll_periods")
    op.drop_index("ix_notifications_business_id", table_name="notifications")
    op.drop_index("ix_leave_types_business_id", table_name="leave_types")
    op.drop_index("ix_leave_requests_business_id", table_name="leave_requests")
    op.drop_index("ix_invoices_business_id", table_name="invoices")
    op.drop_index("ix_expenses_business_id", table_name="expenses")
    op.drop_index("ix_employees_business_id", table_name="employees")
    op.drop_index("ix_departments_business_id", table_name="departments")

    op.drop_column("users", "avatar_url")
