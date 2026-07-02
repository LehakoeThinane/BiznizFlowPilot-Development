"""Lead request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeadBase(BaseModel):
    """Shared lead fields."""

    customer_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    status: str = Field(default="new", pattern="^(new|contacted|qualified|won|lost)$")
    source: Optional[str] = Field(None, max_length=255)
    value: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=2000)


class LeadCreate(LeadBase):
    """Create lead request."""

    pass


class LeadUpdate(BaseModel):
    """Update lead request."""

    customer_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(new|contacted|qualified|won|lost)$")
    source: Optional[str] = Field(None, max_length=255)
    value: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=2000)


class LeadResponse(LeadBase):
    """Lead response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    created_at: datetime
    updated_at: datetime

class LeadListResponse(BaseModel):
    """List of leads response."""

    items: list[LeadResponse]
    total: int
    skip: int
    limit: int
