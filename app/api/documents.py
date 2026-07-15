"""Document API routes - file attachments on any entity."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.integrations.object_storage import ObjectStorageError
from app.schemas.auth import CurrentUser
from app.schemas.document import DocumentDownloadResponse, DocumentListResponse, DocumentResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


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
        return doc
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
    docs = service.list_by_entity(current_user.business_id, current_user, entity_type, entity_id)
    return DocumentListResponse(items=[DocumentResponse.model_validate(d) for d in docs], total=len(docs))


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
