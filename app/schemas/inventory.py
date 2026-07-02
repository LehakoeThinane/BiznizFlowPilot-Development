"""Inventory request/response schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    """Shared location fields."""

    name: str = Field(..., max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    location_type: str = Field(default="warehouse", max_length=50)
    address: Optional[Dict[str, Any]] = None
    is_active: bool = True
    meta_data: Dict[str, Any] = Field(default_factory=dict)


class LocationCreate(LocationBase):
    """Create location request."""

    pass


class LocationUpdate(BaseModel):
    """Update location request."""

    name: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    location_type: Optional[str] = Field(None, max_length=50)
    address: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    meta_data: Optional[Dict[str, Any]] = None


class LocationResponse(LocationBase):
    """Location response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime


class StockLevelBase(BaseModel):
    """Shared stock level fields."""

    product_id: UUID
    location_id: UUID
    quantity: int = Field(default=0)
    reserved: int = Field(default=0)
    reorder_point: int = Field(default=10)
    reorder_quantity: int = Field(default=50)
    last_counted_at: Optional[datetime] = None
    last_counted_by: Optional[UUID] = None


class StockLevelCreate(StockLevelBase):
    """Create stock level request."""

    pass


class StockLevelUpdate(BaseModel):
    """Update stock level request."""

    quantity: Optional[int] = None
    reserved: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    last_counted_at: Optional[datetime] = None
    last_counted_by: Optional[UUID] = None


class StockLevelResponse(StockLevelBase):
    """Stock level response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    available: int
    created_at: datetime
    updated_at: datetime


class StockAdjustment(BaseModel):
    """Stock adjustment request."""

    product_id: UUID
    location_id: UUID
    quantity_change: int
    reason: Optional[str] = None
