"""Document sharing API - create/revoke external share links, and the
public (unauthenticated) redemption endpoint recipients actually click."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.document_share import (
    DocumentShareLinkCreate,
    DocumentShareLinkListResponse,
    DocumentShareLinkResponse,
)
from app.services.document_share import DocumentShareService

router = APIRouter(tags=["document-sharing"])
# Separate router for the public redemption endpoint - must never be wrapped
# with an auth dependency (e.g. require_active_trial) at include time.
public_router = APIRouter(tags=["document-sharing-public"])


def _to_response(link) -> DocumentShareLinkResponse:
    return DocumentShareLinkResponse(
        id=link.id,
        document_id=link.document_id,
        url=f"{settings.api_base_url}/api/v1/share/{link.token}",
        created_by=link.created_by,
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


@router.post("/api/v1/documents/{document_id}/share", response_model=DocumentShareLinkResponse, status_code=201)
def create_share_link(
    document_id: UUID,
    data: DocumentShareLinkCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = DocumentShareService(db)
        link = service.create_link(current_user.business_id, current_user, document_id, data.expires_in_days)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not link:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(link)


@router.get("/api/v1/documents/{document_id}/share", response_model=DocumentShareLinkListResponse)
def list_share_links(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = DocumentShareService(db)
    links = service.list_links(current_user.business_id, current_user, document_id)
    return DocumentShareLinkListResponse(items=[_to_response(link) for link in links])


@router.delete("/api/v1/documents/share/{link_id}", status_code=204)
def revoke_share_link(
    link_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = DocumentShareService(db)
        revoked = service.revoke_link(current_user.business_id, current_user, link_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not revoked:
        raise HTTPException(status_code=404, detail="Share link not found")


@public_router.get("/api/v1/share/{token}", include_in_schema=False)
def redeem_share_link(token: str, db: Annotated[Session, Depends(get_db)]):
    """Public, unauthenticated endpoint an external recipient actually clicks.
    No auth dependency on purpose - the token itself is the credential."""
    service = DocumentShareService(db)
    url = service.resolve_public_download(token)
    if not url:
        raise HTTPException(status_code=404, detail="This link is invalid, expired, or has been revoked")
    return RedirectResponse(url)
