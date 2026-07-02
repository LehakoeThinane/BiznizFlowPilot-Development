"""Purchase order request/response schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class POLineItemBase(BaseModel):
    """Shared purchase order line item fields."""

    product_id: Optional[UUID] = None
    quantity_ordered: int
    quantity_received: int = 0
    unit_cost: Decimal
    tax_rate: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    subtotal: Decimal
    notes: Optional[str] = None


class POLineItemCreate(POLineItemBase):
    """Create purchase order line item request."""

    pass


class POLineItemResponse(POLineItemBase):
    """Purchase order line item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_id: UUID
    created_at: datetime
    updated_at: datetime


class POBase(BaseModel):
    """Shared purchase order fields."""

    po_number: str = Field(..., max_length=50)
    supplier_id: Optional[UUID] = None
    status: str = Field(default="draft", pattern="^(draft|sent|confirmed|partially_received|received|cancelled)$")
    order_date: Optional[datetime] = None
    expected_date: Optional[date] = None
    received_date: Optional[date] = None
    subtotal: Decimal = Decimal("0.00")
    tax_total: Decimal = Decimal("0.00")
    shipping_cost: Decimal = Decimal("0.00")
    total_cost: Decimal
    notes: Optional[str] = None
    receiving_location_id: Optional[UUID] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[UUID] = None


class POCreate(POBase):
    """Create purchase order request."""

    line_items: List[POLineItemCreate] = Field(default_factory=list)


class POUpdate(BaseModel):
    """Update purchase order request."""

    supplier_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(draft|sent|confirmed|partially_received|received|cancelled)$")
    expected_date: Optional[date] = None
    received_date: Optional[date] = None
    subtotal: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    notes: Optional[str] = None
    receiving_location_id: Optional[UUID] = None
    meta_data: Optional[Dict[str, Any]] = None


class POResponse(POBase):
    """Purchase order response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime
    line_items: List[POLineItemResponse] = []


class POListResponse(BaseModel):
    """List of purchase orders response."""

    items: list[POResponse]
    total: int
    skip: int
    limit: int
