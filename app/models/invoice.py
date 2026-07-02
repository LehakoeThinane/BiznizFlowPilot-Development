"""Invoice models."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

_invoice_status = ENUM(
    "draft", "sent", "paid", "overdue", "cancelled", "void",
    name="invoice_status", create_type=False,
)


class Invoice(BaseModel):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_biz_status", "business_id", "status"),
        Index("ix_invoices_customer", "customer_id"),
    )

    business_id      = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number   = Column(String(50), nullable=False)
    customer_id      = Column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    sales_order_id   = Column(Uuid, ForeignKey("sales_orders.id", ondelete="SET NULL"), nullable=True)

    status           = Column(_invoice_status, nullable=False, server_default="draft")
    issue_date       = Column(Date, nullable=False)
    due_date         = Column(Date, nullable=True)
    payment_terms    = Column(String(100), nullable=True)

    subtotal         = Column(Numeric(12, 2), nullable=False, server_default="0")
    tax_amount       = Column(Numeric(12, 2), nullable=False, server_default="0")
    discount_amount  = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_amount     = Column(Numeric(12, 2), nullable=False, server_default="0")

    notes            = Column(Text, nullable=True)
    paid_at          = Column(Date, nullable=True)
    sent_at          = Column(DateTime(timezone=True), nullable=True)

    customer   = relationship("Customer", foreign_keys=[customer_id])
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLineItem(BaseModel):
    __tablename__ = "invoice_line_items"

    invoice_id      = Column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description     = Column(String(255), nullable=False)
    quantity        = Column(Numeric(10, 3), nullable=False, server_default="1")
    unit_price      = Column(Numeric(12, 2), nullable=False)
    discount_percent= Column(Numeric(5, 2), nullable=False, server_default="0")
    tax_rate        = Column(Numeric(5, 2), nullable=False, server_default="0")
    subtotal        = Column(Numeric(12, 2), nullable=False)

    invoice = relationship("Invoice", back_populates="line_items")
