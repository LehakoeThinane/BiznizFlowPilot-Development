"""LeadGenSchedule request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeadGenScheduleCreate(BaseModel):
    """Create a saved lead-gen search."""

    query: str = Field(..., min_length=2, max_length=255)
    max_results: int = Field(default=15, ge=1, le=20)


class LeadGenScheduleUpdate(BaseModel):
    """Update a saved lead-gen search."""

    query: str | None = Field(None, min_length=2, max_length=255)
    max_results: int | None = Field(None, ge=1, le=20)
    active: bool | None = None


class LeadGenScheduleResponse(BaseModel):
    """Saved lead-gen search response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    query: str
    max_results: int
    active: bool


class LeadGenScheduleListResponse(BaseModel):
    """List of saved lead-gen searches."""

    items: list[LeadGenScheduleResponse]
    total: int
