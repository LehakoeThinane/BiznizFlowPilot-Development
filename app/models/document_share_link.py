"""DocumentShareLink model - a revocable, expiring external share link for a Document."""

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class DocumentShareLink(BaseModel):
    """A token granting time-limited, no-login-required access to one Document.

    Deliberately has no business_id - the whole point is external, unauthenticated
    access; tenant safety comes from the token being an unguessable random value
    (see app/services/document_share.py), not from a business_id filter.
    """

    __tablename__ = "document_share_links"

    document_id = Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    document = relationship("Document")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<DocumentShareLink id={self.id} document_id={self.document_id}>"
