"""Messaging service - direct (1:1) chat between colleagues."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.messaging import Conversation, Message
from app.models.user import User
from app.repositories.messaging import ConversationRepository
from app.schemas.auth import CurrentUser
from app.schemas.messaging import ConversationSummary, LastMessagePreview, OtherUser


class MessagingService:
    """Direct-message service.

    🧨 RBAC: Any active user in a business can message any other active user
    in that same business — no role gate, matching open internal messaging.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ConversationRepository(db)

    def get_or_create_direct_conversation(self, business_id: UUID, current_user: CurrentUser, other_user_id: UUID) -> Conversation:
        if other_user_id == current_user.user_id:
            raise ValueError("Cannot start a conversation with yourself")

        other = (
            self.db.query(User)
            .filter(User.id == other_user_id, User.business_id == business_id, User.is_active.is_(True))
            .first()
        )
        if not other:
            raise LookupError("User not found")

        existing = self.repo.find_direct_conversation(business_id, current_user.user_id, other_user_id)
        if existing:
            return existing

        conversation = self.repo.create(business_id=business_id)
        self.repo.add_participant(conversation.id, current_user.user_id)
        self.repo.add_participant(conversation.id, other_user_id)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def summarize(self, conversation: Conversation, current_user_id: UUID) -> ConversationSummary:
        other_participant = next((p for p in conversation.participants if p.user_id != current_user_id), None)
        my_participant = next((p for p in conversation.participants if p.user_id == current_user_id), None)

        other_user = other_participant.user if other_participant else None
        last = self.repo.latest_message(conversation.id)
        unread = self.repo.unread_count_for_conversation(
            conversation.id, current_user_id, my_participant.last_read_at if my_participant else None,
        )
        return ConversationSummary(
            id=conversation.id,
            other_user=OtherUser(
                id=other_user.id if other_user else current_user_id,
                full_name=other_user.full_name if other_user else "Unknown",
                email=other_user.email if other_user else "",
            ),
            last_message=LastMessagePreview(
                content=last.content, created_at=last.created_at, sender_id=last.sender_id,
            ) if last else None,
            unread_count=unread,
        )

    def list_conversations(self, business_id: UUID, current_user: CurrentUser) -> list[ConversationSummary]:
        conversations = self.repo.list_for_user(business_id, current_user.user_id)
        summaries = [self.summarize(c, current_user.user_id) for c in conversations]
        summaries.sort(
            key=lambda s: s.last_message.created_at if s.last_message else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return summaries

    def _require_participant(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID) -> Conversation:
        conversation = self.repo.get(business_id=business_id, entity_id=conversation_id)
        if not conversation:
            raise LookupError("Conversation not found")
        if not self.repo.get_participant(conversation_id, current_user.user_id):
            raise ValueError("Permission denied: You are not part of this conversation")
        return conversation

    def list_messages(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, since: datetime | None = None, limit: int = 50) -> list[Message]:
        self._require_participant(business_id, current_user, conversation_id)
        return self.repo.list_messages(conversation_id, since=since, limit=limit)

    def send_message(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, content: str) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        message = self.repo.add_message(conversation_id, current_user.user_id, content)
        self.db.commit()
        self.db.refresh(message)
        return message

    def mark_read(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID) -> None:
        self._require_participant(business_id, current_user, conversation_id)
        self.repo.mark_read(conversation_id, current_user.user_id, datetime.now(timezone.utc))
        self.db.commit()

    def unread_count(self, business_id: UUID, current_user: CurrentUser) -> int:
        return self.repo.total_unread_count(business_id, current_user.user_id)
