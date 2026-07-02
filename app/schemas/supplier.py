"""Supplier request/response schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SupplierBase(BaseModel):
    """Shared supplier fields."""

    name: str = Field(..., max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[Dict[str, Any]] = None
    payment_terms: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    rating: Optional[int] = None
    notes: Optional[str] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)


class SupplierCreate(SupplierBase):
    """Create supplier request."""

    pass


class SupplierUpdate(BaseModel):
    """Update supplier request."""

    name: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[Dict[str, Any]] = None
    payment_terms: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    rating: Optional[int] = None
    notes: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


class SupplierResponse(SupplierBase):
    """Supplier response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    """List of suppliers response."""

    items: list[SupplierResponse]
    total: int
    skip: int
    limit: int
