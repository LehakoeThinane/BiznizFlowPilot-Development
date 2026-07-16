"""Checkout-style document editing: lock -> edit externally -> check in a new
version, with prior versions archived and downloadable.

🧨 RBAC:
- Check out: anyone with access to the document (has_access), same gate as
  downloading it.
- Check in / cancel checkout: only whoever currently holds the checkout, or
  an owner/manager (admin override, e.g. someone left mid-edit).
- Version history visibility: same as has_access.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES
from app.integrations import object_storage
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.repositories.document import DocumentRepository
from app.repositories.document_version import DocumentVersionRepository
from app.schemas.auth import CurrentUser
from app.services.document import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.services.document_access import DocumentAccessService
from app.services.event import EventService


class DocumentCheckoutService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self.version_repo = DocumentVersionRepository(db)
        self.access_service = DocumentAccessService(db)
        self.event_service = EventService(db)

    @staticmethod
    def _can_override_lock(doc: Document, current_user: CurrentUser) -> bool:
        is_holder = doc.checked_out_by is not None and str(doc.checked_out_by) == str(current_user.user_id)
        return is_holder or current_user.role in PRIVILEGED_ROLES

    def check_out(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> Document | None:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if not self.access_service.has_access(doc, current_user):
            raise PermissionError("This document is restricted - request access first")
        if doc.checked_out_by is not None and str(doc.checked_out_by) != str(current_user.user_id):
            raise ValueError("This document is already checked out by someone else")

        doc.checked_out_by = current_user.user_id
        doc.checked_out_at = datetime.now(timezone.utc)

        self.event_service.create_event(
            business_id=business_id,
            event_type=EventType.CUSTOM,
            entity_type=doc.entity_type,
            entity_id=doc.entity_id,
            actor_id=current_user.user_id,
            description=f"Checked out {doc.filename} for editing",
            commit=False,
        )
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def cancel_checkout(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> Document | None:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if doc.checked_out_by is None:
            return doc
        if not self._can_override_lock(doc, current_user):
            raise PermissionError("Only whoever checked this out, or an owner/manager, can release it")

        doc.checked_out_by = None
        doc.checked_out_at = None
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def check_in(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        document_id: UUID,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> Document | None:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if doc.checked_out_by is None:
            raise ValueError("This document isn't checked out - check it out first")
        if not self._can_override_lock(doc, current_user):
            raise PermissionError("Only whoever checked this out, or an owner/manager, can check in a new version")

        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit")
        if not content:
            raise ValueError("File is empty")
        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"'{extension or 'unknown'}' files are not allowed. Allowed types: {allowed}")

        # Archive the current state as a version before overwriting it.
        self.version_repo.create(
            document_id=doc.id,
            version_number=doc.version,
            uploaded_by=doc.uploaded_by,
            filename=doc.filename,
            content_type=doc.content_type,
            size_bytes=doc.size_bytes,
            storage_key=doc.storage_key,
        )

        new_storage_key = object_storage.upload(business_id, doc.entity_type, doc.entity_id, filename, content, content_type or "")

        doc.filename = filename
        doc.content_type = content_type
        doc.size_bytes = len(content)
        doc.storage_key = new_storage_key
        doc.version += 1
        doc.checked_out_by = None
        doc.checked_out_at = None

        self.event_service.create_event(
            business_id=business_id,
            event_type=EventType.CUSTOM,
            entity_type=doc.entity_type,
            entity_id=doc.entity_id,
            actor_id=current_user.user_id,
            description=f"Checked in {filename} (v{doc.version})",
            commit=False,
        )
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def list_versions(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> list[DocumentVersion]:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return []
        if not self.access_service.has_access(doc, current_user):
            raise PermissionError("This document is restricted - request access first")
        return self.version_repo.list_for_document(document_id)

    def get_version_download_url(
        self, business_id: UUID, current_user: CurrentUser, document_id: UUID, version_id: UUID
    ) -> str | None:
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if not self.access_service.has_access(doc, current_user):
            raise PermissionError("This document is restricted - request access first")

        version = self.version_repo.get(version_id)
        if not version or str(version.document_id) != str(document_id):
            return None
        return object_storage.presigned_download_url(version.storage_key, version.filename)
