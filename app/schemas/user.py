"""User schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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


class PresenceOut(BaseModel):
    """Computed presence - see app/services/presence.py's compute_presence().

    `status` here may be 'offline', even though that value is never stored
    on User.status - offline is derived from last_seen_at staleness, not a
    value a user picks (see StatusUpdateRequest below).
    """

    model_config = ConfigDict(from_attributes=True)

    status: str
    status_text: str | None = None
    last_seen_at: datetime | None = None
    is_online: bool


class StatusUpdateRequest(BaseModel):
    """Body for PATCH /users/me/status."""

    status: str = Field(..., pattern="^(online|away|busy|in_meeting|custom)$")
    status_text: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def _validate_custom_text(self) -> "StatusUpdateRequest":
        if self.status == "custom" and not (self.status_text or "").strip():
            raise ValueError("status_text is required when status is 'custom'")
        if self.status != "custom":
            self.status_text = None
        return self


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
    avatar_url: str | None = None
    presence: PresenceOut

class UserListResponse(BaseModel):
    """Paginated user list response."""

    total: int
    items: list[UserResponse]
