"""Document share-link request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentShareLinkCreate(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=30)


class DocumentShareLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    url: str
    created_by: Optional[UUID] = None
    expires_at: datetime
    created_at: datetime


class DocumentShareLinkListResponse(BaseModel):
    items: list[DocumentShareLinkResponse]
