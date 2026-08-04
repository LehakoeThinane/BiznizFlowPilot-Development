"""Add configurable deduction/benefit types and timesheets for Payroll.

Revision ID: 20260803_42
Revises: 20260803_41
Create Date: 2026-08-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260803_42"
down_revision = "20260803_41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ENUM types ───────────────────────────────────────────────────────────
    postgresql.ENUM("fixed_amount", "percent_of_gross",
                    name="pay_component_calculation").create(op.get_bind(), checkfirst=True)

    _calc = postgresql.ENUM("fixed_amount", "percent_of_gross",
                            name="pay_component_calculation", create_type=False)

    # ── Deduction / benefit type catalogs ───────────────────────────────────
    op.create_table(
        "deduction_types",
        sa.Column("id",             sa.UUID(), nullable=False),
        sa.Column("business_id",    sa.UUID(), nullable=False),
        sa.Column("name",           sa.String(100), nullable=False),
        sa.Column("calculation",    _calc, nullable=False, server_default="fixed_amount"),
        sa.Column("default_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active",      sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deduction_types_biz", "deduction_types", ["business_id"])

    op.create_table(
        "benefit_types",
        sa.Column("id",             sa.UUID(), nullable=False),
        sa.Column("business_id",    sa.UUID(), nullable=False),
        sa.Column("name",           sa.String(100), nullable=False),
        sa.Column("calculation",    _calc, nullable=False, server_default="fixed_amount"),
        sa.Column("default_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active",      sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benefit_types_biz", "benefit_types", ["business_id"])

    # ── Per-employee assignments ─────────────────────────────────────────────
    op.create_table(
        "employee_deductions",
        sa.Column("id",                sa.UUID(), nullable=False),
        sa.Column("business_id",       sa.UUID(), nullable=False),
        sa.Column("employee_id",       sa.UUID(), nullable=False),
        sa.Column("deduction_type_id", sa.UUID(), nullable=False),
        sa.Column("amount_override",   sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active",         sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],       ["businesses.id"],      ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"],       ["employees.id"],       ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deduction_type_id"], ["deduction_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_deductions_employee", "employee_deductions", ["employee_id", "is_active"])

    op.create_table(
        "employee_benefits",
        sa.Column("id",              sa.UUID(), nullable=False),
        sa.Column("business_id",     sa.UUID(), nullable=False),
        sa.Column("employee_id",     sa.UUID(), nullable=False),
        sa.Column("benefit_type_id", sa.UUID(), nullable=False),
        sa.Column("amount_override", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active",       sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],     ["businesses.id"],    ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"],     ["employees.id"],     ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["benefit_type_id"], ["benefit_types.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_benefits_employee", "employee_benefits", ["employee_id", "is_active"])

    # ── Timesheets ───────────────────────────────────────────────────────────
    op.create_table(
        "timesheets",
        sa.Column("id",           sa.UUID(), nullable=False),
        sa.Column("business_id",  sa.UUID(), nullable=False),
        sa.Column("employee_id",  sa.UUID(), nullable=False),
        sa.Column("work_date",    sa.Date(), nullable=False),
        sa.Column("hours_worked", sa.Numeric(5, 2), nullable=False),
        sa.Column("notes",        sa.Text(), nullable=True),
        sa.Column("created_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"],  ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timesheets_employee_date", "timesheets", ["employee_id", "work_date"])


def downgrade() -> None:
    op.drop_table("timesheets")
    op.drop_table("employee_benefits")
    op.drop_table("employee_deductions")
    op.drop_table("benefit_types")
    op.drop_table("deduction_types")

    postgresql.ENUM(name="pay_component_calculation").drop(op.get_bind(), checkfirst=True)
