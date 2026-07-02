"""Product request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    """Shared product fields."""

    sku: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    product_type: str = Field(default="physical", pattern="^(physical|digital|service)$")
    category: Optional[str] = Field(None, max_length=100)
    unit_price: Decimal
    cost_price: Optional[Decimal] = None
    tax_rate: Decimal = Decimal("0.00")
    is_active: bool = True
    track_inventory: bool = True
    barcode: Optional[str] = Field(None, max_length=100)
    weight: Optional[Decimal] = None
    weight_unit: str = Field(default="kg", max_length=10)
    dimensions: Optional[Dict[str, Any]] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)


class ProductCreate(ProductBase):
    """Create product request."""

    pass


class ProductUpdate(BaseModel):
    """Update product request."""

    sku: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    product_type: Optional[str] = Field(None, pattern="^(physical|digital|service)$")
    category: Optional[str] = Field(None, max_length=100)
    unit_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    track_inventory: Optional[bool] = None
    barcode: Optional[str] = Field(None, max_length=100)
    weight: Optional[Decimal] = None
    weight_unit: Optional[str] = Field(None, max_length=10)
    dimensions: Optional[Dict[str, Any]] = None
    meta_data: Optional[Dict[str, Any]] = None


class ProductResponse(ProductBase):
    """Product response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """List of products response."""

    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
