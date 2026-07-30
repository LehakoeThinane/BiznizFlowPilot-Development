"""Customer portal schemas - authenticated access management + the public,
unauthenticated document list/download surface."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.document import DocumentResponse


class CustomerPortalAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    created_at: datetime
    last_accessed_at: Optional[datetime] = None


class CustomerPortalAccessCreateResponse(CustomerPortalAccessResponse):
    """Only ever returned once, from the create/regenerate call - includes
    the raw portal URL, which is never persisted or retrievable again."""

    portal_url: str


class CustomerPortalDetailResponse(BaseModel):
    """The public portal page's data - deliberately excludes anything that
    would identify the customer's own account beyond their display name."""

    customer_name: str
    business_name: str
    documents: list[DocumentResponse]


class CustomerPortalDownloadResponse(BaseModel):
    url: str
    expires_in: int
