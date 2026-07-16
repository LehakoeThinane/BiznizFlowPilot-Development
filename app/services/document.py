"""Document service - upload/list/delete files attached to any entity.

🧨 RBAC: Any authenticated business member can upload/view (team
collaboration, same permissiveness as the activity-timeline notes).
Delete is restricted to the uploader themselves, or owner/manager.
"""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES
from app.integrations import object_storage
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.schemas.auth import CurrentUser
from app.services.document_access import DocumentAccessService
from app.services.event import EventService

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB

# Ordinary business-document types only - deliberately excludes anything
# executable (.exe, .bat, .sh, .js, .msi, etc.) as a defense-in-depth
# measure against uploading/distributing malware through the platform.
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".csv", ".txt", ".zip",
}


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self._event_service = EventService(db)
        self._access_service = DocumentAccessService(db)

    def upload(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        entity_type: str,
        entity_id: UUID,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> Document:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit")
        if not content:
            raise ValueError("File is empty")

        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"'{extension or 'unknown'}' files are not allowed. Allowed types: {allowed}")

        storage_key = object_storage.upload(business_id, entity_type, entity_id, filename, content, content_type or "")

        doc = self.repo.create(
            business_id=business_id,
            commit=False,
            entity_type=entity_type,
            entity_id=entity_id,
            uploaded_by=current_user.user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_key=storage_key,
        )

        # Surface the upload in the same activity timeline as notes/status
        # changes for this entity (e.g. a lead's or task's detail panel).
        self._event_service.create_event(
            business_id=business_id,
            event_type=EventType.CUSTOM,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=current_user.user_id,
            description=f"Uploaded document: {filename}",
            commit=False,
        )

        self.db.commit()
        self.db.refresh(doc)
        return doc

    def list_by_entity(self, business_id: UUID, current_user: CurrentUser, entity_type: str, entity_id: UUID) -> list[Document]:
        return self.repo.get_by_entity(business_id, entity_type, entity_id)

    def list_library(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        entity_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """Business-wide document listing for the standalone library page."""
        return self.repo.get_library(business_id, entity_type=entity_type, search=search, skip=skip, limit=limit)

    def get_download_url(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> str | None:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if not self._access_service.has_access(doc, current_user):
            raise PermissionError("This document is restricted - request access first")
        return object_storage.presigned_download_url(doc.storage_key, doc.filename)

    def has_access(self, doc: Document, current_user: CurrentUser) -> bool:
        return self._access_service.has_access(doc, current_user)

    def delete(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> bool:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return False

        is_uploader = doc.uploaded_by is not None and str(doc.uploaded_by) == str(current_user.user_id)
        if not is_uploader and current_user.role not in PRIVILEGED_ROLES:
            raise PermissionError("Only the uploader or an owner/manager can delete this document")

        object_storage.delete(doc.storage_key)
        return self.repo.delete(business_id=business_id, entity_id=document_id)
