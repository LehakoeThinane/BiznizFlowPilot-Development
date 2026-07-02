"""Add Finance, HR & Payroll, Invoicing, and Notifications tables.

Revision ID: 20260504_01
Revises: 20260429_01
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260504_01"
down_revision = "20260429_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ENUM types ───────────────────────────────────────────────────────────
    postgresql.ENUM("full_time", "part_time", "contractor", "intern",
                    name="employment_type").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("monthly", "hourly", "annual",
                    name="salary_type").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("pending", "approved", "rejected", "cancelled",
                    name="leave_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("draft", "processing", "completed", "cancelled",
                    name="payroll_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("draft", "finalized",
                    name="payslip_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("draft", "sent", "paid", "overdue", "cancelled", "void",
                    name="invoice_status").create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("low_stock", "overdue_task", "order_status", "payroll", "leave", "system",
                    name="notification_type").create(op.get_bind(), checkfirst=True)

    # ── Finance ──────────────────────────────────────────────────────────────
    op.create_table(
        "expense_categories",
        sa.Column("id",          sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name",        sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active",   sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_categories_biz", "expense_categories", ["business_id"])

    op.create_table(
        "expenses",
        sa.Column("id",          sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("date",        sa.Date(), nullable=False),
        sa.Column("amount",      sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("vendor",      sa.String(150), nullable=True),
        sa.Column("reference",   sa.String(100), nullable=True),
        sa.Column("paid_by",     sa.UUID(), nullable=True),
        sa.Column("notes",       sa.Text(), nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["expense_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["paid_by"],     ["users.id"],              ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_biz_date",   "expenses", ["business_id", "date"])
    op.create_index("ix_expenses_category",   "expenses", ["category_id"])

    # ── HR ───────────────────────────────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id",          sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name",        sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active",   sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    _et = postgresql.ENUM("full_time", "part_time", "contractor", "intern", name="employment_type", create_type=False)
    _st = postgresql.ENUM("monthly", "hourly", "annual", name="salary_type", create_type=False)

    op.create_table(
        "employees",
        sa.Column("id",              sa.UUID(), nullable=False),
        sa.Column("business_id",     sa.UUID(), nullable=False),
        sa.Column("department_id",   sa.UUID(), nullable=True),
        sa.Column("user_id",         sa.UUID(), nullable=True),
        sa.Column("first_name",      sa.String(100), nullable=False),
        sa.Column("last_name",       sa.String(100), nullable=False),
        sa.Column("email",           sa.String(255), nullable=True),
        sa.Column("phone",           sa.String(50),  nullable=True),
        sa.Column("position",        sa.String(150), nullable=True),
        sa.Column("national_id",     sa.String(50),  nullable=True),
        sa.Column("tax_number",      sa.String(50),  nullable=True),
        sa.Column("bank_account",    sa.String(100), nullable=True),
        sa.Column("employment_type", _et, nullable=False, server_default="full_time"),
        sa.Column("salary_type",     _st, nullable=False, server_default="monthly"),
        sa.Column("gross_salary",    sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("start_date",      sa.Date(), nullable=True),
        sa.Column("end_date",        sa.Date(), nullable=True),
        sa.Column("is_active",       sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes",           sa.Text(), nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],   ["businesses.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"],       ["users.id"],       ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employees_biz_active",   "employees", ["business_id", "is_active"])
    op.create_index("ix_employees_department",   "employees", ["department_id"])

    op.create_table(
        "leave_types",
        sa.Column("id",           sa.UUID(), nullable=False),
        sa.Column("business_id",  sa.UUID(), nullable=False),
        sa.Column("name",         sa.String(100), nullable=False),
        sa.Column("default_days", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("is_paid",      sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active",    sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    _ls = postgresql.ENUM("pending", "approved", "rejected", "cancelled", name="leave_status", create_type=False)

    op.create_table(
        "leave_requests",
        sa.Column("id",             sa.UUID(), nullable=False),
        sa.Column("business_id",    sa.UUID(), nullable=False),
        sa.Column("employee_id",    sa.UUID(), nullable=False),
        sa.Column("leave_type_id",  sa.UUID(), nullable=True),
        sa.Column("start_date",     sa.Date(), nullable=False),
        sa.Column("end_date",       sa.Date(), nullable=False),
        sa.Column("days_requested", sa.Numeric(5, 1), nullable=False),
        sa.Column("status",         _ls, nullable=False, server_default="pending"),
        sa.Column("reason",         sa.Text(), nullable=True),
        sa.Column("approved_by",    sa.UUID(), nullable=True),
        sa.Column("approved_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes",          sa.Text(), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],   ["businesses.id"],  ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"],   ["employees.id"],   ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"],   ["users.id"],       ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_requests_employee", "leave_requests", ["employee_id", "status"])

    _ps = postgresql.ENUM("draft", "processing", "completed", "cancelled", name="payroll_status", create_type=False)

    op.create_table(
        "payroll_periods",
        sa.Column("id",               sa.UUID(), nullable=False),
        sa.Column("business_id",      sa.UUID(), nullable=False),
        sa.Column("period_year",      sa.Integer(), nullable=False),
        sa.Column("period_month",     sa.Integer(), nullable=False),
        sa.Column("status",           _ps, nullable=False, server_default="draft"),
        sa.Column("total_gross",      sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_net",        sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("processed_by",     sa.UUID(), nullable=True),
        sa.Column("processed_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes",            sa.Text(), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"],     ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payroll_periods_biz", "payroll_periods", ["business_id", "period_year", "period_month"])

    _pss = postgresql.ENUM("draft", "finalized", name="payslip_status", create_type=False)

    op.create_table(
        "payslips",
        sa.Column("id",                sa.UUID(), nullable=False),
        sa.Column("business_id",       sa.UUID(), nullable=False),
        sa.Column("payroll_period_id", sa.UUID(), nullable=False),
        sa.Column("employee_id",       sa.UUID(), nullable=False),
        sa.Column("basic_pay",         sa.Numeric(12, 2), nullable=False),
        sa.Column("overtime_pay",      sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("bonus",             sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("gross_pay",         sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_deduction",     sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("uif_deduction",     sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions",  sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_deductions",  sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_pay",           sa.Numeric(12, 2), nullable=False),
        sa.Column("status",            _pss, nullable=False, server_default="draft"),
        sa.Column("notes",             sa.Text(), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],       ["businesses.id"],      ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payroll_period_id"], ["payroll_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"],       ["employees.id"],       ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payslips_period_employee", "payslips", ["payroll_period_id", "employee_id"])

    # ── Invoices ─────────────────────────────────────────────────────────────
    _is = postgresql.ENUM("draft", "sent", "paid", "overdue", "cancelled", "void", name="invoice_status", create_type=False)

    op.create_table(
        "invoices",
        sa.Column("id",             sa.UUID(), nullable=False),
        sa.Column("business_id",    sa.UUID(), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("customer_id",    sa.UUID(), nullable=True),
        sa.Column("sales_order_id", sa.UUID(), nullable=True),
        sa.Column("status",         _is, nullable=False, server_default="draft"),
        sa.Column("issue_date",     sa.Date(), nullable=False),
        sa.Column("due_date",       sa.Date(), nullable=True),
        sa.Column("payment_terms",  sa.String(100), nullable=True),
        sa.Column("subtotal",       sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount",     sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount",sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount",   sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes",          sa.Text(), nullable=True),
        sa.Column("paid_at",        sa.Date(), nullable=True),
        sa.Column("sent_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],    ["businesses.id"],   ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"],    ["customers.id"],    ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoices_biz_status", "invoices", ["business_id", "status"])
    op.create_index("ix_invoices_customer",   "invoices", ["customer_id"])

    op.create_table(
        "invoice_line_items",
        sa.Column("id",               sa.UUID(), nullable=False),
        sa.Column("invoice_id",       sa.UUID(), nullable=False),
        sa.Column("description",      sa.String(255), nullable=False),
        sa.Column("quantity",         sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unit_price",       sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate",         sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal",         sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",       sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_invoice_line_items_invoice", "invoice_line_items", ["invoice_id"])

    # ── Notifications ────────────────────────────────────────────────────────
    _nt = postgresql.ENUM("low_stock", "overdue_task", "order_status", "payroll", "leave", "system",
                          name="notification_type", create_type=False)

    op.create_table(
        "notifications",
        sa.Column("id",           sa.UUID(), nullable=False),
        sa.Column("business_id",  sa.UUID(), nullable=False),
        sa.Column("user_id",      sa.UUID(), nullable=False),
        sa.Column("type",         _nt, nullable=False),
        sa.Column("title",        sa.String(200), nullable=False),
        sa.Column("message",      sa.Text(), nullable=False),
        sa.Column("is_read",      sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("action_url",   sa.String(300), nullable=True),
        sa.Column("related_type", sa.String(50), nullable=True),
        sa.Column("related_id",   sa.UUID(), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"],     ["users.id"],      ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"])
    op.create_index("ix_notifications_business",  "notifications", ["business_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("payslips")
    op.drop_table("payroll_periods")
    op.drop_table("leave_requests")
    op.drop_table("leave_types")
    op.drop_table("employees")
    op.drop_table("departments")
    op.drop_table("expenses")
    op.drop_table("expense_categories")

    for name in ["notification_type", "invoice_status", "payslip_status",
                 "payroll_status", "leave_status", "salary_type", "employment_type"]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
