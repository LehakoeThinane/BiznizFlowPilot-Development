"""Document request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Document response - metadata only, not the file content itself."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    entity_type: str
    entity_id: UUID
    uploaded_by: Optional[UUID] = None
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    """List of documents attached to an entity."""

    items: list[DocumentResponse]
    total: int


class DocumentDownloadResponse(BaseModel):
    """A short-lived signed URL for downloading a document."""

    url: str
    expires_in: int
