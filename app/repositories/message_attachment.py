"""MessageAttachment repository - data access layer."""

from app.models.message_attachment import MessageAttachment
from app.repositories.base import BaseRepository


class MessageAttachmentRepository(BaseRepository[MessageAttachment]):
    """MessageAttachment repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db):
        super().__init__(db, MessageAttachment)
