"""Organization and subsidiary schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationResponse(BaseModel):
    """Read-only organization summary, visible to any authenticated user in it."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    plan_tier: str
    subscription_status: str
    domains: list[str] = Field(default_factory=list)


class OrganizationUpdate(BaseModel):
    """Update organization request (IT Admin only)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrganizationDomainCreate(BaseModel):
    """Add an authorized email domain to the organization."""

    domain: str = Field(..., min_length=3, max_length=255, pattern=r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    is_primary: bool = False


class OrganizationDomainResponse(BaseModel):
    """Authorized domain response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain: str
    verified: bool
    is_primary: bool


class SubsidiaryCreate(BaseModel):
    """Create subsidiary request."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = None


class SubsidiaryUpdate(BaseModel):
    """Update subsidiary request."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None


class SubsidiaryResponse(BaseModel):
    """Subsidiary (Business) response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    email: str
    phone: str | None
    is_primary_subsidiary: bool
    is_active: bool
    user_count: int = 0


class SubsidiaryListResponse(BaseModel):
    """List of subsidiaries."""

    total: int
    items: list[SubsidiaryResponse]
