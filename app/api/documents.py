"""Document API routes - file attachments on any entity."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.integrations.object_storage import ObjectStorageError
from app.models.document import Document
from app.schemas.auth import CurrentUser
from app.schemas.document import (
    DocumentAccessRequestListResponse,
    DocumentAccessRequestResponse,
    DocumentDownloadResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentRestrictUpdate,
    DocumentVersionListResponse,
)
from app.services.document import DocumentService
from app.services.document_access import DocumentAccessService
from app.services.document_checkout import DocumentCheckoutService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _to_response(doc: Document, current_user: CurrentUser, access_service: DocumentAccessService) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        business_id=doc.business_id,
        entity_type=doc.entity_type,
        entity_id=doc.entity_id,
        uploaded_by=doc.uploaded_by,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        restricted=doc.restricted,
        has_access=access_service.has_access(doc, current_user),
        version=doc.version,
        checked_out_by=doc.checked_out_by,
        checked_out_at=doc.checked_out_at,
        created_at=doc.created_at,
    )


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    entity_type: str = Form(...),
    entity_id: UUID = Form(...),
    file: UploadFile = File(...),
):
    """Upload a file attached to an entity (lead, task, invoice, etc.)."""
    content = await file.read()
    try:
        service = DocumentService(db)
        doc = service.upload(
            current_user.business_id, current_user,
            entity_type, entity_id,
            file.filename or "upload", content, file.content_type,
        )
        db.commit()
        return _to_response(doc, current_user, DocumentAccessService(db))
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=DocumentListResponse)
def list_documents(
    entity_type: str,
    entity_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """List documents attached to an entity."""
    service = DocumentService(db)
    access_service = DocumentAccessService(db)
    docs = service.list_by_entity(current_user.business_id, current_user, entity_type, entity_id)
    return DocumentListResponse(
        items=[_to_response(d, current_user, access_service) for d in docs], total=len(docs),
    )


@router.get("/library", response_model=DocumentListResponse)
def list_document_library(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    entity_type: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    """Business-wide document listing for the standalone library page."""
    service = DocumentService(db)
    access_service = DocumentAccessService(db)
    docs, total = service.list_library(
        current_user.business_id, current_user, entity_type=entity_type, search=search, skip=skip, limit=limit,
    )
    return DocumentListResponse(items=[_to_response(d, current_user, access_service) for d in docs], total=total)


@router.get("/{document_id}/download-url", response_model=DocumentDownloadResponse)
def get_download_url(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get a short-lived signed URL for downloading a document directly from storage."""
    try:
        service = DocumentService(db)
        url = service.get_download_url(current_user.business_id, current_user, document_id)
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not url:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDownloadResponse(url=url, expires_in=300)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a document. Only the uploader or an owner/manager may delete."""
    try:
        service = DocumentService(db)
        deleted = service.delete(current_user.business_id, current_user, document_id)
        db.commit()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ObjectStorageError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        db.rollback()
        raise

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.patch("/{document_id}/restrict", response_model=DocumentResponse)
def set_document_restricted(
    document_id: UUID,
    data: DocumentRestrictUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Toggle whether a document requires approved access to view/download."""
    try:
        access_service = DocumentAccessService(db)
        doc = access_service.set_restricted(current_user.business_id, current_user, document_id, data.restricted)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc, current_user, access_service)


@router.post("/{document_id}/access-requests", response_model=DocumentAccessRequestResponse, status_code=201)
def request_document_access(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Request access to a restricted document - notifies owner/manager for review."""
    try:
        req = DocumentAccessService(db).request_access(current_user.business_id, current_user, document_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return req


@router.get("/{document_id}/access-requests", response_model=DocumentAccessRequestListResponse)
def list_document_access_requests(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """List access requests for a document. Owner/manager only."""
    try:
        requests = DocumentAccessService(db).list_requests(current_user.business_id, current_user, document_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return DocumentAccessRequestListResponse(items=requests)


@router.post("/access-requests/{request_id}/approve", response_model=DocumentAccessRequestResponse)
def approve_document_access_request(
    request_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve a pending access request. Owner/manager only."""
    try:
        req = DocumentAccessService(db).approve(current_user.business_id, current_user, request_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")
    return req


@router.post("/access-requests/{request_id}/deny", response_model=DocumentAccessRequestResponse)
def deny_document_access_request(
    request_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Deny a pending access request. Owner/manager only."""
    try:
        req = DocumentAccessService(db).deny(current_user.business_id, current_user, request_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")
    return req


@router.post("/{document_id}/checkout", response_model=DocumentResponse)
def check_out_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Lock a document for editing - checkout-style, one editor at a time."""
    try:
        service = DocumentCheckoutService(db)
        doc = service.check_out(current_user.business_id, current_user, document_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc, current_user, DocumentAccessService(db))


@router.post("/{document_id}/checkout/cancel", response_model=DocumentResponse)
def cancel_document_checkout(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Release a checkout without checking in a new version."""
    try:
        service = DocumentCheckoutService(db)
        doc = service.cancel_checkout(current_user.business_id, current_user, document_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc, current_user, DocumentAccessService(db))


@router.post("/{document_id}/checkin", response_model=DocumentResponse)
async def check_in_document(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload a new version, archiving the current one, and release the checkout."""
    content = await file.read()
    try:
        service = DocumentCheckoutService(db)
        doc = service.check_in(
            current_user.business_id, current_user, document_id,
            file.filename or "upload", content, file.content_type,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc, current_user, DocumentAccessService(db))


@router.get("/{document_id}/versions", response_model=DocumentVersionListResponse)
def list_document_versions(
    document_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """List archived prior versions of a document, newest first."""
    try:
        versions = DocumentCheckoutService(db).list_versions(current_user.business_id, current_user, document_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return DocumentVersionListResponse(items=versions)


@router.get("/{document_id}/versions/{version_id}/download-url", response_model=DocumentDownloadResponse)
def get_version_download_url(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get a short-lived signed URL for downloading a specific prior version."""
    try:
        url = DocumentCheckoutService(db).get_version_download_url(
            current_user.business_id, current_user, document_id, version_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ObjectStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not url:
        raise HTTPException(status_code=404, detail="Version not found")
    return DocumentDownloadResponse(url=url, expires_in=300)
