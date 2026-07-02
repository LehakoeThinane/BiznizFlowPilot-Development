"""Customer request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerBase(BaseModel):
    """Shared customer fields."""

    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    company: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    """Create customer request."""

    pass


class CustomerUpdate(BaseModel):
    """Update customer request."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    company: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class CustomerResponse(CustomerBase):
    """Customer response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime

class CustomerListResponse(BaseModel):
    """List of customers response."""

    items: list[CustomerResponse]
    total: int
    skip: int
    limit: int
