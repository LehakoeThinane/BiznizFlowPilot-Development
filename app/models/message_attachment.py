"""MessageAttachment model - a file (document/image/video/audio) sent in a chat message."""

from sqlalchemy import BigInteger, Column, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class MessageAttachment(BaseModel):
    """A file uploaded and attached to a direct-message conversation.

    Stored in Cloudflare R2 (see app/integrations/object_storage.py) -
    `storage_key` is the R2 object key, not the file content itself.
    """

    __tablename__ = "message_attachments"

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    filename = Column(String(255), nullable=False, doc="Original filename")
    content_type = Column(String(100), nullable=True, doc="MIME type")
    size_bytes = Column(BigInteger, nullable=False, doc="File size in bytes")
    storage_key = Column(String(500), nullable=False, unique=True, doc="R2 object key")
    kind = Column(String(20), nullable=False, doc="document | image | video | audio")

    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        return f"<MessageAttachment id={self.id} filename='{self.filename}'>"
