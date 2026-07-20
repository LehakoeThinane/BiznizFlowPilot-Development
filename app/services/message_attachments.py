"""Message attachment service - upload a file (document/image/video/audio) into a chat conversation."""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations import object_storage
from app.models.messaging import Conversation, Message
from app.repositories.message_attachment import MessageAttachmentRepository
from app.repositories.messaging import ConversationRepository
from app.schemas.auth import CurrentUser

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm"}
# Ordinary business-document types only - deliberately excludes anything
# executable, matching the same defense-in-depth posture as DocumentService.
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".zip", ".svg",
}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | DOCUMENT_EXTENSIONS

MAX_BYTES_BY_KIND = {
    "document": 25 * 1024 * 1024,
    "image": 25 * 1024 * 1024,
    "video": 64 * 1024 * 1024,
    "audio": 16 * 1024 * 1024,
}


def _kind_for(filename: str, content_type: str | None) -> str:
    """Classify by MIME type first (reliable for browser-captured photos/recordings),
    falling back to extension only when content_type is missing/generic."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/"):
        return "audio"

    extension = os.path.splitext(filename)[1].lower()
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in AUDIO_EXTENSIONS:
        return "audio"
    return "document"


class MessageAttachmentService:
    """Upload a file and post it as a message in a conversation.

    🧨 RBAC: Same as MessagingService - only participants of the
    conversation may upload into it.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = MessageAttachmentRepository(db)
        self.conversations = ConversationRepository(db)

    def _require_participant(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID) -> Conversation:
        conversation = self.conversations.get(business_id=business_id, entity_id=conversation_id)
        if not conversation:
            raise LookupError("Conversation not found")
        if not self.conversations.get_participant(conversation_id, current_user.user_id):
            raise PermissionError("Permission denied: You are not part of this conversation")
        return conversation

    def upload(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        conversation_id: UUID,
        filename: str,
        content: bytes,
        content_type: str | None,
        caption: str | None = None,
    ) -> Message:
        self._require_participant(business_id, current_user, conversation_id)

        if not content:
            raise ValueError("File is empty")

        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"'{extension or 'unknown'}' files are not allowed. Allowed types: {allowed}")

        kind = _kind_for(filename, content_type)
        max_bytes = MAX_BYTES_BY_KIND[kind]
        if len(content) > max_bytes:
            raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)}MB upload limit for {kind} attachments")

        storage_key = object_storage.upload(business_id, "message", conversation_id, filename, content, content_type or "")

        attachment = self.repo.create(
            business_id=business_id,
            commit=False,
            conversation_id=conversation_id,
            uploaded_by=current_user.user_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_key=storage_key,
            kind=kind,
        )

        message = self.conversations.add_typed_message(
            conversation_id, current_user.user_id, kind, content=caption, attachment_id=attachment.id,
        )
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_download_url(self, business_id: UUID, current_user: CurrentUser, attachment_id: UUID) -> str | None:
        attachment = self.repo.get(business_id=business_id, entity_id=attachment_id)
        if not attachment:
            return None
        if not self.conversations.get_participant(attachment.conversation_id, current_user.user_id):
            raise PermissionError("Permission denied: You are not part of this conversation")
        return object_storage.presigned_download_url(attachment.storage_key, attachment.filename)
