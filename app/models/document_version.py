"""DocumentVersion model - an archived snapshot of a Document's prior state.

`Document` itself always represents the *current* version (so everything
that already references a Document.id - the activity timeline, share
links, access requests - keeps working unmodified across check-ins).
Old versions are archived here before being overwritten, keeping their
own storage_key so historical downloads still work.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class DocumentVersion(BaseModel):
    __tablename__ = "document_versions"
    __table_args__ = (
        Index("ix_document_versions_document_id", "document_id"),
    )

    document_id = Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)

    uploaded_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(String(500), nullable=False, unique=True)

    document = relationship("Document")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<DocumentVersion document_id={self.document_id} version_number={self.version_number}>"
