"""Invitation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationCreate(BaseModel):
    """Create invitation request."""

    email: EmailStr
    role: str = Field(default="staff", pattern="^(owner|manager|staff|it_admin)$")
    business_id: UUID | None = Field(
        default=None,
        description="Required for IT Admins inviting into a subsidiary other than their own; ignored for owner/manager",
    )


class InvitationResponse(BaseModel):
    """Invitation response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime


class InvitationListResponse(BaseModel):
    """Paginated invitation list response."""

    total: int
    items: list[InvitationResponse]


class InvitationValidateResponse(BaseModel):
    """Public pre-accept validation response - no sensitive data."""

    organization_name: str
    business_name: str
    masked_email: str
    role: str


class InvitationAcceptRequest(BaseModel):
    """Request body to accept an invitation."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
