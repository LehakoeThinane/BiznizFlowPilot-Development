"""Messaging repository - data access layer for direct-message conversations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.models.messaging import Conversation, ConversationParticipant, Message
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Conversation repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, Conversation)

    def list_for_user(self, business_id: UUID, user_id: UUID) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
            .filter(Conversation.business_id == business_id, ConversationParticipant.user_id == user_id)
            .all()
        )

    def find_direct_conversation(self, business_id: UUID, user_a: UUID, user_b: UUID) -> Conversation | None:
        """Find an existing 1:1 conversation between exactly these two users, if any."""
        cp_a = aliased(ConversationParticipant)
        cp_b = aliased(ConversationParticipant)
        candidates = (
            self.db.query(Conversation)
            .join(cp_a, cp_a.conversation_id == Conversation.id)
            .join(cp_b, cp_b.conversation_id == Conversation.id)
            .filter(
                Conversation.business_id == business_id,
                cp_a.user_id == user_a,
                cp_b.user_id == user_b,
            )
            .all()
        )
        for convo in candidates:
            participant_ids = {p.user_id for p in convo.participants}
            if participant_ids == {user_a, user_b}:
                return convo
        return None

    # ── Participants ─────────────────────────────────────────────────────

    def get_participant(self, conversation_id: UUID, user_id: UUID) -> ConversationParticipant | None:
        return (
            self.db.query(ConversationParticipant)
            .filter(ConversationParticipant.conversation_id == conversation_id, ConversationParticipant.user_id == user_id)
            .first()
        )

    def add_participant(self, conversation_id: UUID, user_id: UUID) -> ConversationParticipant:
        participant = ConversationParticipant(conversation_id=conversation_id, user_id=user_id)
        self.db.add(participant)
        return participant

    def mark_read(self, conversation_id: UUID, user_id: UUID, when: datetime) -> None:
        participant = self.get_participant(conversation_id, user_id)
        if participant:
            participant.last_read_at = when

    # ── Messages ─────────────────────────────────────────────────────────

    def list_messages(self, conversation_id: UUID, since: datetime | None = None, limit: int = 50) -> list[Message]:
        q = self.db.query(Message).filter(Message.conversation_id == conversation_id)
        if since is not None:
            q = q.filter(Message.created_at > since)
        return q.order_by(Message.created_at.asc()).limit(limit).all()

    def latest_message(self, conversation_id: UUID) -> Message | None:
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .first()
        )

    def add_message(self, conversation_id: UUID, sender_id: UUID, content: str, is_ai_reply: bool = False) -> Message:
        message = Message(conversation_id=conversation_id, sender_id=sender_id, content=content, is_ai_reply=is_ai_reply)
        self.db.add(message)
        return message

    def add_typed_message(self, conversation_id: UUID, sender_id: UUID, message_type: str, content: str | None = None, **refs) -> Message:
        """Create a non-text message (attachment/contact/event/poll/sticker).

        `refs` carries whichever of attachment_id/shared_customer_id/
        shared_meeting_id/poll_id/sticker_key applies to `message_type`.
        """
        message = Message(conversation_id=conversation_id, sender_id=sender_id, message_type=message_type, content=content, **refs)
        self.db.add(message)
        return message

    def unread_count_for_conversation(self, conversation_id: UUID, user_id: UUID, last_read_at: datetime | None) -> int:
        q = self.db.query(func.count(Message.id)).filter(
            Message.conversation_id == conversation_id,
            or_(Message.sender_id != user_id, Message.sender_id.is_(None)),
        )
        if last_read_at is not None:
            q = q.filter(Message.created_at > last_read_at)
        return q.scalar() or 0

    def total_unread_count(self, business_id: UUID, user_id: UUID) -> int:
        rows = (
            self.db.query(ConversationParticipant.conversation_id, ConversationParticipant.last_read_at)
            .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
            .filter(Conversation.business_id == business_id, ConversationParticipant.user_id == user_id)
            .all()
        )
        total = 0
        for conversation_id, last_read_at in rows:
            total += self.unread_count_for_conversation(conversation_id, user_id, last_read_at)
        return total
