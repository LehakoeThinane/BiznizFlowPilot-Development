"""Add purchase_requisitions and purchase_requisition_line_items tables.

Revision ID: 20260713_21
Revises: 20260713_20
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260713_21"
down_revision = "20260713_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM(
        "pending", "approved", "rejected", "cancelled", "converted",
        name="purchase_requisition_status",
    ).create(op.get_bind(), checkfirst=True)

    _prs = postgresql.ENUM(
        "pending", "approved", "rejected", "cancelled", "converted",
        name="purchase_requisition_status", create_type=False,
    )

    op.create_table(
        "purchase_requisitions",
        sa.Column("id",                       sa.UUID(), nullable=False),
        sa.Column("business_id",               sa.UUID(), nullable=False),
        sa.Column("requested_by",               sa.UUID(), nullable=True),
        sa.Column("supplier_id",                sa.UUID(), nullable=True),
        sa.Column("title",                      sa.String(255), nullable=False),
        sa.Column("justification",              sa.Text(), nullable=True),
        sa.Column("estimated_total",            sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status",                     _prs, nullable=False, server_default="pending"),
        sa.Column("approved_by",                sa.UUID(), nullable=True),
        sa.Column("approved_at",                sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason",           sa.Text(), nullable=True),
        sa.Column("converted_purchase_order_id", sa.UUID(), nullable=True),
        sa.Column("created_at",                 sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",                 sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"],               ["businesses.id"],      ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"],               ["users.id"],           ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"],                ["suppliers.id"],       ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"],                ["users.id"],           ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["converted_purchase_order_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_requisitions_business_id", "purchase_requisitions", ["business_id"])
    op.create_index("ix_purchase_requisitions_status", "purchase_requisitions", ["business_id", "status"])
    op.create_index("ix_purchase_requisitions_requested_by", "purchase_requisitions", ["requested_by"])
    op.create_index("ix_purchase_requisitions_supplier_id", "purchase_requisitions", ["supplier_id"])

    op.create_table(
        "purchase_requisition_line_items",
        sa.Column("id",                    sa.UUID(), nullable=False),
        sa.Column("requisition_id",         sa.UUID(), nullable=False),
        sa.Column("product_id",             sa.UUID(), nullable=True),
        sa.Column("description",            sa.String(255), nullable=False),
        sa.Column("quantity",               sa.Integer(), nullable=False),
        sa.Column("estimated_unit_cost",    sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at",             sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at",             sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["requisition_id"], ["purchase_requisitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"],     ["products.id"],              ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_requisition_line_items_requisition_id", "purchase_requisition_line_items", ["requisition_id"])
    op.create_index("ix_purchase_requisition_line_items_product_id", "purchase_requisition_line_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("purchase_requisition_line_items")
    op.drop_table("purchase_requisitions")
    postgresql.ENUM(name="purchase_requisition_status").drop(op.get_bind(), checkfirst=True)
