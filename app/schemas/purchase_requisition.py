"""Purchase requisition request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PRLineItemBase(BaseModel):
    """Shared purchase requisition line item fields."""

    product_id: Optional[UUID] = None
    description: str = Field(..., max_length=255)
    quantity: int = Field(..., gt=0)
    estimated_unit_cost: Optional[Decimal] = None


class PRLineItemCreate(PRLineItemBase):
    """Create purchase requisition line item request."""

    pass


class PRLineItemResponse(PRLineItemBase):
    """Purchase requisition line item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requisition_id: UUID
    created_at: datetime
    updated_at: datetime


class PRBase(BaseModel):
    """Shared purchase requisition fields."""

    title: str = Field(..., max_length=255)
    justification: Optional[str] = None
    supplier_id: Optional[UUID] = None
    estimated_total: Decimal = Decimal("0.00")


class PRCreate(PRBase):
    """Submit a purchase requisition request."""

    line_items: List[PRLineItemCreate] = Field(default_factory=list)


class PRStatusUpdate(BaseModel):
    """Approve, reject, or cancel a purchase requisition."""

    status: str = Field(..., pattern="^(approved|rejected|cancelled)$")
    rejection_reason: Optional[str] = None


class PRResponse(PRBase):
    """Purchase requisition response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    requested_by: Optional[UUID] = None
    status: str
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    converted_purchase_order_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    line_items: List[PRLineItemResponse] = []


class PRListResponse(BaseModel):
    """List of purchase requisitions response."""

    items: list[PRResponse]
    total: int
    skip: int
    limit: int
