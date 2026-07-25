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
    restricted: bool = False
    has_access: bool = True
    version: int = 1
    checked_out_by: Optional[UUID] = None
    checked_out_at: Optional[datetime] = None
    created_at: datetime


class DocumentListResponse(BaseModel):
    """List of documents attached to an entity."""

    items: list[DocumentResponse]
    total: int


class DocumentDownloadResponse(BaseModel):
    """A short-lived signed URL for downloading a document."""

    url: str
    expires_in: int


class DocumentRestrictUpdate(BaseModel):
    restricted: bool


class DocumentComposeRequest(BaseModel):
    """Create a new, empty in-app document attached to an entity."""

    entity_type: str
    entity_id: UUID
    title: str = "Untitled Document"


class DocumentDraftUpdate(BaseModel):
    """Autosave payload - the editor's current (unsaved-as-a-version) content."""

    content_html: str


class DocumentAccessRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    user_id: UUID
    status: str
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class DocumentAccessRequestListResponse(BaseModel):
    items: list[DocumentAccessRequestResponse]


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    uploaded_by: Optional[UUID] = None
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    created_at: datetime


class DocumentVersionListResponse(BaseModel):
    items: list[DocumentVersionResponse]
