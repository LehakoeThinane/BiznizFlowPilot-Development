"""DocumentAccessRequest repository.

Not a BaseRepository subclass - like DocumentShareLink, this model has no
business_id (tenant safety comes from the service layer checking the
parent Document's business_id before any of these methods are reached).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document_access_request import DocumentAccessRequest


class DocumentAccessRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, request_id: UUID) -> DocumentAccessRequest | None:
        return self.db.query(DocumentAccessRequest).filter(DocumentAccessRequest.id == request_id).first()

    def get_by_document_and_user(self, document_id: UUID, user_id: UUID) -> DocumentAccessRequest | None:
        return (
            self.db.query(DocumentAccessRequest)
            .filter(DocumentAccessRequest.document_id == document_id, DocumentAccessRequest.user_id == user_id)
            .first()
        )

    def create(self, document_id: UUID, user_id: UUID) -> DocumentAccessRequest:
        req = DocumentAccessRequest(document_id=document_id, user_id=user_id, status="pending")
        self.db.add(req)
        self.db.flush()
        return req

    def list_for_document(self, document_id: UUID) -> list[DocumentAccessRequest]:
        return (
            self.db.query(DocumentAccessRequest)
            .filter(DocumentAccessRequest.document_id == document_id)
            .order_by(DocumentAccessRequest.created_at.desc())
            .all()
        )

    def has_approved_access(self, document_id: UUID, user_id: UUID) -> bool:
        return (
            self.db.query(DocumentAccessRequest.id)
            .filter(
                DocumentAccessRequest.document_id == document_id,
                DocumentAccessRequest.user_id == user_id,
                DocumentAccessRequest.status == "approved",
            )
            .first()
            is not None
        )
