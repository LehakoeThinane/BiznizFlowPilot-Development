"""Folder API routes - nested containers for documents not tied to a CRM record."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.folder import FolderCreate, FolderListResponse, FolderRename, FolderResponse
from app.services.folder import FolderService

router = APIRouter(prefix="/api/v1/folders", tags=["folders"])


@router.post("", response_model=FolderResponse, status_code=201)
def create_folder(
    data: FolderCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = FolderService(db)
        folder = service.create(current_user.business_id, current_user, data.name, data.parent_folder_id)
        db.commit()
        return folder
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=FolderListResponse)
def list_folders(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    parent_folder_id: UUID | None = None,
):
    """List immediate sub-folders of a folder, or top-level folders when parent_folder_id is omitted."""
    service = FolderService(db)
    folders = service.list_children(current_user.business_id, current_user, parent_folder_id)
    return FolderListResponse(items=folders)


@router.get("/{folder_id}", response_model=FolderResponse)
def get_folder(
    folder_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = FolderService(db)
    folder = service.get(current_user.business_id, current_user, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.patch("/{folder_id}", response_model=FolderResponse)
def rename_folder(
    folder_id: UUID,
    data: FolderRename,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = FolderService(db)
        folder = service.rename(current_user.business_id, current_user, folder_id, data.name)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.delete("/{folder_id}", status_code=204)
def delete_folder(
    folder_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = FolderService(db)
        deleted = service.delete(current_user.business_id, current_user, folder_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=404, detail="Folder not found")
