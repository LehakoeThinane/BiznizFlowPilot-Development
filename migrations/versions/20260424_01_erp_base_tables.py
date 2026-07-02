"""Add ERP base tables: products, inventory, sales and purchasing.

Revision ID: 20260424_01
Revises: 20260421_01
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260424_01"
down_revision = "20260421_01"
branch_labels = None
depends_on = None


# Used for explicit CREATE TYPE (with checkfirst)
product_type_enum = postgresql.ENUM(
    "physical", "digital", "service",
    name="product_type",
)
order_status_enum = postgresql.ENUM(
    "draft", "confirmed", "processing", "shipped", "delivered", "cancelled",
    name="order_status",
)
purchase_order_status_enum = postgresql.ENUM(
    "draft", "sent", "confirmed", "partially_received", "received", "cancelled",
    name="purchase_order_status",
)

# Used inside create_table — create_type=False prevents a duplicate CREATE TYPE
_pt = postgresql.ENUM("physical", "digital", "service", name="product_type", create_type=False)
_os = postgresql.ENUM(
    "draft", "confirmed", "processing", "shipped", "delivered", "cancelled",
    name="order_status", create_type=False,
)
_pos = postgresql.ENUM(
    "draft", "sent", "confirmed", "partially_received", "received", "cancelled",
    name="purchase_order_status", create_type=False,
)


def upgrade() -> None:
    """Create ERP foundation tables."""
    bind = op.get_bind()

    product_type_enum.create(bind, checkfirst=True)
    order_status_enum.create(bind, checkfirst=True)
    purchase_order_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_type", _pt, nullable=False, server_default=sa.text("'physical'")),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("track_inventory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("weight", sa.Numeric(10, 2), nullable=True),
        sa.Column("weight_unit", sa.String(length=10), nullable=False, server_default=sa.text("'kg'")),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "sku", name="uq_business_product_sku"),
    )
    op.create_index("ix_products_business_id", "products", ["business_id"], unique=False)
    op.create_index("ix_products_active", "products", ["business_id", "is_active"], unique=False)
    op.create_index("ix_products_category", "products", ["business_id", "category"], unique=False)

    op.create_table(
        "inventory_locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("location_type", sa.String(length=50), nullable=False, server_default=sa.text("'warehouse'")),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_business_location_code"),
    )
    op.create_index("ix_inventory_locations_business_id", "inventory_locations", ["business_id"], unique=False)

    op.create_table(
        "stock_levels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("available", sa.Integer(), sa.Computed("quantity - reserved", persisted=True), nullable=False),
        sa.Column("reorder_point", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("reorder_quantity", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("last_counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_counted_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["last_counted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["inventory_locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "location_id", name="uq_product_location_stock"),
    )
    op.create_index("ix_stock_levels_product_id", "stock_levels", ["product_id"], unique=False)
    op.create_index("ix_stock_levels_location_id", "stock_levels", ["location_id"], unique=False)
    op.create_index(
        "ix_stock_levels_low_stock",
        "stock_levels",
        ["location_id", "product_id"],
        unique=False,
        postgresql_where=sa.text("(quantity - reserved) < reorder_point"),
    )

    op.create_table(
        "suppliers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payment_terms", sa.String(length=100), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "code", name="uq_business_supplier_code"),
    )
    op.create_index("ix_suppliers_business_id", "suppliers", ["business_id"], unique=False)
    op.create_index("ix_suppliers_active", "suppliers", ["business_id", "is_active"], unique=False)

    op.create_table(
        "sales_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("status", _os, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expected_ship_date", sa.Date(), nullable=True),
        sa.Column("actual_ship_date", sa.Date(), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("actual_delivery_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_total", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("shipping_cost", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("shipping_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("billing_address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tracking_number", sa.String(length=100), nullable=True),
        sa.Column("carrier", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "order_number", name="uq_business_order_number"),
    )
    op.create_index("ix_sales_orders_business_id", "sales_orders", ["business_id"], unique=False)
    op.create_index("ix_sales_orders_customer_id", "sales_orders", ["customer_id"], unique=False)
    op.create_index("ix_sales_orders_status_date", "sales_orders", ["business_id", "status", "order_date"], unique=False)

    op.create_table(
        "order_line_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("product_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_line_items_order_id", "order_line_items", ["order_id"], unique=False)
    op.create_index("ix_order_line_items_product_id", "order_line_items", ["product_id"], unique=False)

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("status", _pos, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_total", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("shipping_cost", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("receiving_location_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["receiving_location_id"], ["inventory_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "po_number", name="uq_business_po_number"),
    )
    op.create_index("ix_purchase_orders_business_id", "purchase_orders", ["business_id"], unique=False)
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"], unique=False)
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["business_id", "status"], unique=False)

    op.create_table(
        "purchase_order_line_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("po_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_order_line_items_po_id", "purchase_order_line_items", ["po_id"], unique=False)
    op.create_index("ix_purchase_order_line_items_product_id", "purchase_order_line_items", ["product_id"], unique=False)


def downgrade() -> None:
    """Drop ERP foundation tables and enum types."""
    bind = op.get_bind()

    op.drop_index("ix_purchase_order_line_items_product_id", table_name="purchase_order_line_items")
    op.drop_index("ix_purchase_order_line_items_po_id", table_name="purchase_order_line_items")
    op.drop_table("purchase_order_line_items")

    op.drop_index("ix_purchase_orders_status", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_business_id", table_name="purchase_orders")
    op.drop_table("purchase_orders")

    op.drop_index("ix_order_line_items_product_id", table_name="order_line_items")
    op.drop_index("ix_order_line_items_order_id", table_name="order_line_items")
    op.drop_table("order_line_items")

    op.drop_index("ix_sales_orders_status_date", table_name="sales_orders")
    op.drop_index("ix_sales_orders_customer_id", table_name="sales_orders")
    op.drop_index("ix_sales_orders_business_id", table_name="sales_orders")
    op.drop_table("sales_orders")

    op.drop_index("ix_suppliers_active", table_name="suppliers")
    op.drop_index("ix_suppliers_business_id", table_name="suppliers")
    op.drop_table("suppliers")

    op.drop_index("ix_stock_levels_low_stock", table_name="stock_levels")
    op.drop_index("ix_stock_levels_location_id", table_name="stock_levels")
    op.drop_index("ix_stock_levels_product_id", table_name="stock_levels")
    op.drop_table("stock_levels")

    op.drop_index("ix_inventory_locations_business_id", table_name="inventory_locations")
    op.drop_table("inventory_locations")

    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_active", table_name="products")
    op.drop_index("ix_products_business_id", table_name="products")
    op.drop_table("products")

    purchase_order_status_enum.drop(bind, checkfirst=True)
    order_status_enum.drop(bind, checkfirst=True)
    product_type_enum.drop(bind, checkfirst=True)
