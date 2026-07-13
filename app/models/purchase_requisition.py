"""Purchase requisition models - employee purchase requests pending manager approval.

Distinct from PurchaseOrder (which assumes whoever creates it is already
authorized to buy): a requisition is the pre-approval step where staff ask
for something and a manager approves/rejects before it becomes a real PO.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class PurchaseRequisition(BaseModel):
    """An employee's request to purchase something, pending approval."""

    __tablename__ = "purchase_requisitions"

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    supplier_id = Column(Uuid, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    justification = Column(Text, nullable=True)
    estimated_total = Column(Numeric(12, 2), nullable=False, server_default="0")
    status = Column(
        ENUM(
            "pending", "approved", "rejected", "cancelled", "converted",
            name="purchase_requisition_status", create_type=False,
        ),
        nullable=False,
        server_default="pending",
        index=True,
    )
    approved_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    converted_purchase_order_id = Column(
        Uuid, ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )

    line_items = relationship(
        "PurchaseRequisitionLineItem", back_populates="requisition", cascade="all, delete-orphan"
    )
    supplier = relationship("Supplier")

    SAFE_CONTEXT_FIELDS = ("id", "title", "status", "estimated_total")


class PurchaseRequisitionLineItem(BaseModel):
    """Individual requested items within a purchase requisition."""

    __tablename__ = "purchase_requisition_line_items"

    requisition_id = Column(
        Uuid, ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(Uuid, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    estimated_unit_cost = Column(Numeric(10, 2), nullable=True)

    requisition = relationship("PurchaseRequisition", back_populates="line_items")
    product = relationship("Product")

    SAFE_CONTEXT_FIELDS = ("id", "product_id", "description", "quantity", "estimated_unit_cost")
