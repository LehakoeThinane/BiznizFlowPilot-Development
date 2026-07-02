"""Invoice schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvoiceLineItemCreate(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    discount_percent: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("15.00")  # South African standard VAT rate


class InvoiceLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    tax_rate: Decimal
    subtotal: Decimal


class InvoiceCreate(BaseModel):
    customer_id: UUID | None = None
    sales_order_id: UUID | None = None
    issue_date: date
    due_date: date | None = None
    payment_terms: str | None = None
    notes: str | None = None
    line_items: list[InvoiceLineItemCreate] = []


class InvoiceStatusUpdate(BaseModel):
    status: str


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    invoice_number: str
    customer_id: UUID | None
    customer_name: str | None = None
    sales_order_id: UUID | None
    status: str
    issue_date: date
    due_date: date | None
    payment_terms: str | None
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    notes: str | None
    paid_at: date | None
    sent_at: datetime | None
    created_at: datetime
    line_items: list[InvoiceLineItemOut] = []


class InvoiceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    invoice_number: str
    customer_name: str | None = None
    status: str
    issue_date: date
    due_date: date | None
    total_amount: Decimal
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    total: int
    skip: int
    limit: int
