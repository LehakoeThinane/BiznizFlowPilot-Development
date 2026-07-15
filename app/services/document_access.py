"""Document access-request workflow for restricted documents.

🧨 RBAC:
- Toggling a document's `restricted` flag: uploader or owner/manager
  (same rule as delete/share - it's their own upload, or an admin).
- Requesting access: any authenticated business member without access.
- Reviewing (list/approve/deny) requests: owner/manager only - matches
  the same-shape approval workflows already in this codebase (leave
  requests, purchase requisitions), never self-service by the uploader.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import PRIVILEGED_ROLES, require_role
from app.models.document import Document
from app.models.document_access_request import DocumentAccessRequest
from app.repositories.document import DocumentRepository
from app.repositories.document_access_request import DocumentAccessRequestRepository
from app.schemas.auth import CurrentUser
from app.utils.notify import notify_business, notify_user


class DocumentAccessService:
    def __init__(self, db: Session):
        self.db = db
        self.document_repo = DocumentRepository(db)
        self.request_repo = DocumentAccessRequestRepository(db)

    @staticmethod
    def _can_manage(doc: Document, current_user: CurrentUser) -> bool:
        is_uploader = doc.uploaded_by is not None and str(doc.uploaded_by) == str(current_user.user_id)
        return is_uploader or current_user.role in PRIVILEGED_ROLES

    def has_access(self, doc: Document, current_user: CurrentUser) -> bool:
        """Whether the given user can view/download this document right now."""
        if not doc.restricted:
            return True
        if self._can_manage(doc, current_user):
            return True
        return self.request_repo.has_approved_access(doc.id, current_user.user_id)

    def set_restricted(self, business_id: UUID, current_user: CurrentUser, document_id: UUID, restricted: bool) -> Document | None:
        doc = self.document_repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        if not self._can_manage(doc, current_user):
            raise PermissionError("Only the uploader or an owner/manager can change a document's access restriction")

        doc.restricted = restricted
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def request_access(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> DocumentAccessRequest:
        doc = self.document_repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            raise ValueError("Document not found")
        if not doc.restricted:
            raise ValueError("This document is not restricted - no request needed")
        if self._can_manage(doc, current_user):
            raise ValueError("You already have access to this document")

        existing = self.request_repo.get_by_document_and_user(document_id, current_user.user_id)
        if existing:
            if existing.status == "approved":
                raise ValueError("You already have access to this document")
            existing.status = "pending"
            existing.reviewed_by = None
            existing.reviewed_at = None
            req = existing
        else:
            req = self.request_repo.create(document_id, current_user.user_id)

        notify_business(
            self.db, business_id, "system",
            "Document access requested",
            f"{current_user.full_name} requested access to '{doc.filename}'.",
            action_url="/tasks",
            related_type="document_access_request", related_id=req.id,
            roles=PRIVILEGED_ROLES,
        )

        self.db.commit()
        self.db.refresh(req)
        return req

    def list_requests(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> list[DocumentAccessRequest]:
        require_role(current_user, PRIVILEGED_ROLES, "review document access requests")
        doc = self.document_repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return []
        return self.request_repo.list_for_document(document_id)

    def _review(self, business_id: UUID, current_user: CurrentUser, request_id: UUID, new_status: str) -> DocumentAccessRequest | None:
        require_role(current_user, PRIVILEGED_ROLES, "review document access requests")

        req = self.request_repo.get(request_id)
        if not req:
            return None
        doc = self.document_repo.get(business_id=business_id, entity_id=req.document_id)
        if not doc:
            return None

        req.status = new_status
        req.reviewed_by = current_user.user_id
        req.reviewed_at = datetime.now(timezone.utc)

        notify_user(
            self.db, business_id, req.user_id, "system",
            f"Document access {new_status}",
            f"Your request to access '{doc.filename}' was {new_status}.",
            action_url="/tasks",
            related_type="document_access_request", related_id=req.id,
        )

        self.db.commit()
        self.db.refresh(req)
        return req

    def approve(self, business_id: UUID, current_user: CurrentUser, request_id: UUID) -> DocumentAccessRequest | None:
        return self._review(business_id, current_user, request_id, "approved")

    def deny(self, business_id: UUID, current_user: CurrentUser, request_id: UUID) -> DocumentAccessRequest | None:
        return self._review(business_id, current_user, request_id, "denied")
