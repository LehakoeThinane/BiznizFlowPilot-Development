"""Lead-gen search request/response schemas."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.lead import LeadResponse


class LeadGenSearchRequest(BaseModel):
    """Google Places text search request, e.g. "plumbers in Johannesburg"."""

    query: str = Field(..., min_length=2, max_length=255)
    max_results: int = Field(default=10, ge=1, le=20)
    assign_to: Optional[UUID] = None


class LeadGenSearchResponse(BaseModel):
    """Result of a lead-gen search - leads already created and notified."""

    created_count: int
    skipped_duplicates: int
    leads: list[LeadResponse]
