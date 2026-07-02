"""Sales order models for ERP sales module."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class SalesOrder(BaseModel):
    """Customer sales orders."""

    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("business_id", "order_number", name="uq_business_order_number"),
        Index("ix_sales_orders_status_date", "business_id", "status", "order_date"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_number = Column(String(50), nullable=False)
    customer_id = Column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(Uuid, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    status = Column(
        ENUM("draft", "confirmed", "processing", "shipped", "delivered", "cancelled", name="order_status", create_type=False),
        nullable=False,
        server_default="draft",
    )
    order_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expected_ship_date = Column(Date, nullable=True)
    actual_ship_date = Column(Date, nullable=True)
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)
    
    subtotal = Column(Numeric(10, 2), nullable=False, server_default="0")
    tax_total = Column(Numeric(10, 2), nullable=False, server_default="0")
    shipping_cost = Column(Numeric(10, 2), nullable=False, server_default="0")
    discount_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    shipping_address = Column(JSONB, nullable=True)
    billing_address = Column(JSONB, nullable=True)
    tracking_number = Column(String(100), nullable=True)
    carrier = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    meta_data = Column("metadata", JSONB, nullable=False, default=dict)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    line_items = relationship("OrderLineItem", back_populates="order", cascade="all, delete-orphan")
    customer = relationship("Customer")
    lead = relationship("Lead")

    SAFE_CONTEXT_FIELDS = (
        "id",
        "order_number",
        "customer_id",
        "status",
        "order_date",
        "total_amount",
        "tracking_number",
        "carrier",
    )


class OrderLineItem(BaseModel):
    """Individual items within a sales order."""

    __tablename__ = "order_line_items"

    order_id = Column(
        Uuid, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_snapshot = Column(JSONB, nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=False, server_default="0")
    discount_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    tax_rate = Column(Numeric(5, 2), nullable=False, server_default="0")
    tax_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    subtotal = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    order = relationship("SalesOrder", back_populates="line_items")
    product = relationship("Product")

    SAFE_CONTEXT_FIELDS = (
        "id",
        "product_id",
        "quantity",
        "unit_price",
        "subtotal",
    )
