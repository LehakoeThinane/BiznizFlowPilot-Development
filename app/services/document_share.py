"""Document sharing service - create/list/revoke expiring external share links,
and resolve a public token to a signed download URL for the unauthenticated
recipient side.

🧨 RBAC: Only the document's uploader or an owner/manager may create or
revoke a share link - same rule as deleting a document, since an external
link is a materially bigger exposure than in-app visibility.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import PRIVILEGED_ROLES
from app.integrations import object_storage
from app.models.document_share_link import DocumentShareLink
from app.repositories.document import DocumentRepository
from app.repositories.document_share_link import DocumentShareLinkRepository
from app.schemas.auth import CurrentUser

DEFAULT_EXPIRY_DAYS = 7
MAX_EXPIRY_DAYS = 30


def _as_aware_utc(dt: datetime) -> datetime:
    """SQLite (used in tests) doesn't preserve timezone-awareness on
    round-trip even for DateTime(timezone=True) columns - normalize before
    comparing against a tz-aware "now" so this behaves the same in
    SQLite-backed tests and Postgres-backed production."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class DocumentShareService:
    def __init__(self, db: Session):
        self.db = db
        self.document_repo = DocumentRepository(db)
        self.link_repo = DocumentShareLinkRepository(db)

    def _require_share_permission(self, doc, current_user: CurrentUser) -> None:
        is_uploader = doc.uploaded_by is not None and str(doc.uploaded_by) == str(current_user.user_id)
        if not is_uploader and current_user.role not in PRIVILEGED_ROLES:
            raise PermissionError("Only the uploader or an owner/manager can manage sharing for this document")

    def create_link(
        self, business_id: UUID, current_user: CurrentUser, document_id: UUID, expires_in_days: int = DEFAULT_EXPIRY_DAYS
    ) -> DocumentShareLink | None:
        doc = self.document_repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None
        self._require_share_permission(doc, current_user)

        expires_in_days = min(max(expires_in_days, 1), MAX_EXPIRY_DAYS)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        link = self.link_repo.create(document_id, current_user.user_id, token, expires_at)
        self.db.commit()
        self.db.refresh(link)
        return link

    def list_links(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> list[DocumentShareLink]:
        doc = self.document_repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return []
        now = datetime.now(timezone.utc)
        return [
            link for link in self.link_repo.list_for_document(document_id)
            if link.revoked_at is None and _as_aware_utc(link.expires_at) > now
        ]

    def revoke_link(self, business_id: UUID, current_user: CurrentUser, link_id: UUID) -> bool:
        link = self.link_repo.get(link_id)
        if not link:
            return False
        doc = self.document_repo.get(business_id=business_id, entity_id=link.document_id)
        if not doc:
            return False
        self._require_share_permission(doc, current_user)

        link.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def resolve_public_download(self, token: str) -> str | None:
        """Public, unauthenticated path: token -> presigned download URL.

        Returns None if the token is invalid, expired, or revoked - the API
        layer must turn that into a generic 404, never distinguishing why.
        """
        link = self.link_repo.get_by_token(token)
        if not link:
            return None

        now = datetime.now(timezone.utc)
        if link.revoked_at is not None or _as_aware_utc(link.expires_at) < now:
            return None

        doc = self.document_repo.get_by_id_for_public_share(link.document_id)
        if not doc:
            return None

        return object_storage.presigned_download_url(doc.storage_key, doc.filename)
