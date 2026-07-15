"""DocumentShareLink repository.

Not a BaseRepository subclass - this model has no business_id (external
share tokens are intentionally tenant-agnostic; tenant safety is enforced
in the service layer via the parent Document's business_id before a link
is ever created).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document_share_link import DocumentShareLink


class DocumentShareLinkRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, document_id: UUID, created_by: UUID | None, token: str, expires_at: datetime) -> DocumentShareLink:
        link = DocumentShareLink(document_id=document_id, created_by=created_by, token=token, expires_at=expires_at)
        self.db.add(link)
        self.db.flush()
        return link

    def get_by_token(self, token: str) -> DocumentShareLink | None:
        return self.db.query(DocumentShareLink).filter(DocumentShareLink.token == token).first()

    def get(self, link_id: UUID) -> DocumentShareLink | None:
        return self.db.query(DocumentShareLink).filter(DocumentShareLink.id == link_id).first()

    def list_for_document(self, document_id: UUID) -> list[DocumentShareLink]:
        return (
            self.db.query(DocumentShareLink)
            .filter(DocumentShareLink.document_id == document_id)
            .order_by(DocumentShareLink.created_at.desc())
            .all()
        )
