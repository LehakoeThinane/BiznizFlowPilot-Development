"""DocumentAccessRequest model - a request (and, once approved, a standing
grant) for one user to access one restricted Document.

Deliberately a plain String status with a CHECK constraint, not a native
Postgres enum - avoids the enum-migration-drift class of bug hit twice
already tonight for a status set this small and unlikely to grow.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class DocumentAccessRequest(BaseModel):
    __tablename__ = "document_access_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'denied')", name="ck_document_access_requests_status"),
        Index("ix_document_access_requests_doc_user", "document_id", "user_id", unique=True),
    )

    document_id = Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    reviewed_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    document = relationship("Document")
    requester = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self) -> str:
        return f"<DocumentAccessRequest document_id={self.document_id} user_id={self.user_id} status='{self.status}'>"
