"""Document model - a file attached to any entity (lead, task, invoice, etc.)."""

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Document(BaseModel):
    """A file uploaded and attached to some other business entity.

    Stored in Cloudflare R2 (see app/integrations/object_storage.py) -
    `storage_key` is the R2 object key, not the file content itself.
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_business_entity", "business_id", "entity_type", "entity_id"),
    )

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )

    entity_type = Column(
        String(50),
        nullable=False,
        doc="Entity this document is attached to: lead, task, customer, invoice, etc.",
    )

    entity_id = Column(
        Uuid,
        nullable=False,
        doc="ID of the entity this document is attached to",
    )

    uploaded_by = Column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="User who uploaded this document",
    )

    filename = Column(String(255), nullable=False, doc="Original filename")
    content_type = Column(String(100), nullable=True, doc="MIME type")
    size_bytes = Column(BigInteger, nullable=False, doc="File size in bytes")
    storage_key = Column(String(500), nullable=False, unique=True, doc="R2 object key")

    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename='{self.filename}'>"
