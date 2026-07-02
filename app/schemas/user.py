"""User schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Create user request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    role: str = Field(default="staff", pattern="^(owner|manager|staff|it_admin)$")


class UserUpdate(BaseModel):
    """Update user request."""

    first_name: str | None = None
    last_name: str | None = None
    role: str | None = Field(None, pattern="^(owner|manager|staff|it_admin)$")


class UserResponse(BaseModel):
    """User response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool

class UserListResponse(BaseModel):
    """Paginated user list response."""

    total: int
    items: list[UserResponse]
