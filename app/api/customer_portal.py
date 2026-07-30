"""Public (unauthenticated) customer portal endpoints - the durable,
bookmarkable link a client uses to view/download their own documents.
No auth dependency on purpose (mirrors app/api/document_share.py's
public_router): the token itself is the credential. Rate-limited more
strictly in spirit than document_share.py's redemption endpoint, since a
durable token is a much better brute-force target than a 7-day one."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.customer_portal import CustomerPortalDetailResponse, CustomerPortalDownloadResponse
from app.services.customer_portal import CustomerPortalService

public_router = APIRouter(tags=["customer-portal-public"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)


@public_router.get("/api/v1/portal/{token}", response_model=CustomerPortalDetailResponse, include_in_schema=False)
@limiter.limit("20/minute")
def get_portal_documents(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    """No-auth document list for a client portal link. Generic 404 for any
    invalid/revoked token - never distinguish why, same rule as
    document_share.py's public redemption."""
    result = CustomerPortalService(db).list_documents(token)
    if not result:
        raise HTTPException(status_code=404, detail="This link is invalid or has been revoked")

    customer, business_name, documents = result
    return CustomerPortalDetailResponse(customer_name=customer.name, business_name=business_name, documents=documents)


@public_router.get(
    "/api/v1/portal/{token}/documents/{document_id}/download-url",
    response_model=CustomerPortalDownloadResponse,
    include_in_schema=False,
)
@limiter.limit("20/minute")
def get_portal_document_download_url(
    token: str, document_id: UUID, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """Signed download URL for one of this customer's documents - re-checks
    the document actually belongs to the token's own customer_id first."""
    url = CustomerPortalService(db).get_document_download_url(token, document_id)
    if not url:
        raise HTTPException(status_code=404, detail="This link is invalid or has been revoked")
    return CustomerPortalDownloadResponse(url=url, expires_in=300)
