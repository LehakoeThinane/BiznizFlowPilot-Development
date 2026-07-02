"""Purchase order models for ERP purchasing module."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class PurchaseOrder(BaseModel):
    """Purchase orders to suppliers."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("business_id", "po_number", name="uq_business_po_number"),
        Index("ix_purchase_orders_status", "business_id", "status"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    po_number = Column(String(50), nullable=False)
    supplier_id = Column(Uuid, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(
        ENUM("draft", "sent", "confirmed", "partially_received", "received", "cancelled", name="purchase_order_status", create_type=False),
        nullable=False,
        server_default="draft",
    )
    order_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expected_date = Column(Date, nullable=True)
    received_date = Column(Date, nullable=True)
    
    subtotal = Column(Numeric(10, 2), nullable=False, server_default="0")
    tax_total = Column(Numeric(10, 2), nullable=False, server_default="0")
    shipping_cost = Column(Numeric(10, 2), nullable=False, server_default="0")
    total_cost = Column(Numeric(10, 2), nullable=False)
    
    notes = Column(Text, nullable=True)
    receiving_location_id = Column(Uuid, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True)
    meta_data = Column("metadata", JSONB, nullable=False, default=dict)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    line_items = relationship("PurchaseOrderLineItem", back_populates="purchase_order", cascade="all, delete-orphan")
    supplier = relationship("Supplier")
    receiving_location = relationship("InventoryLocation")

    SAFE_CONTEXT_FIELDS = (
        "id",
        "po_number",
        "supplier_id",
        "status",
        "order_date",
        "total_cost",
    )


class PurchaseOrderLineItem(BaseModel):
    """Individual items within a purchase order."""

    __tablename__ = "purchase_order_line_items"

    po_id = Column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quantity_ordered = Column(Integer, nullable=False)
    quantity_received = Column(Integer, nullable=False, server_default="0")
    unit_cost = Column(Numeric(10, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=False, server_default="0")
    tax_amount = Column(Numeric(10, 2), nullable=False, server_default="0")
    subtotal = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="line_items")
    product = relationship("Product")

    SAFE_CONTEXT_FIELDS = (
        "id",
        "product_id",
        "quantity_ordered",
        "quantity_received",
        "unit_cost",
        "subtotal",
    )
