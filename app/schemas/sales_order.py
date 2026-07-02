"""Sales order request/response schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LineItemBase(BaseModel):
    """Shared order line item fields."""

    product_id: Optional[UUID] = None
    product_snapshot: Optional[Dict[str, Any]] = None
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    subtotal: Decimal
    notes: Optional[str] = None


class LineItemCreate(LineItemBase):
    """Create order line item request."""

    pass


class LineItemResponse(LineItemBase):
    """Order line item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    created_at: datetime
    updated_at: datetime


class OrderBase(BaseModel):
    """Shared sales order fields."""

    order_number: str = Field(..., max_length=50)
    customer_id: Optional[UUID] = None
    lead_id: Optional[UUID] = None
    status: str = Field(default="draft", pattern="^(draft|confirmed|processing|shipped|delivered|cancelled)$")
    order_date: Optional[datetime] = None
    expected_ship_date: Optional[date] = None
    actual_ship_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    subtotal: Decimal = Decimal("0.00")
    tax_total: Decimal = Decimal("0.00")
    shipping_cost: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    total_amount: Decimal
    shipping_address: Optional[Dict[str, Any]] = None
    billing_address: Optional[Dict[str, Any]] = None
    tracking_number: Optional[str] = Field(None, max_length=100)
    carrier: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[UUID] = None


class OrderCreate(BaseModel):
    """Create sales order request — server generates order_number and totals."""

    customer_id: Optional[UUID] = None
    lead_id: Optional[UUID] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    line_items: List[LineItemCreate] = Field(default_factory=list)


class OrderUpdate(BaseModel):
    """Update sales order request."""

    customer_id: Optional[UUID] = None
    lead_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(draft|confirmed|processing|shipped|delivered|cancelled)$")
    expected_ship_date: Optional[date] = None
    actual_ship_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    subtotal: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    shipping_address: Optional[Dict[str, Any]] = None
    billing_address: Optional[Dict[str, Any]] = None
    tracking_number: Optional[str] = Field(None, max_length=100)
    carrier: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


class OrderResponse(OrderBase):
    """Sales order response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime
    line_items: List[LineItemResponse] = []


class OrderListResponse(BaseModel):
    """List of sales orders response."""

    items: list[OrderResponse]
    total: int
    skip: int
    limit: int
