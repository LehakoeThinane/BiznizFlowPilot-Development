"""Repository for chat conversations and messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.chat import ChatConversation, ChatMessage


class ChatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Conversations ────────────────────────────────────────────────────────

    def create_conversation(
        self,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatConversation:
        conv = ChatConversation(
            business_id=business_id,
            user_id=user_id,
            title=title,
        )
        self.db.add(conv)
        self.db.flush()
        return conv

    def get_conversation(
        self,
        conversation_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> ChatConversation | None:
        return (
            self.db.query(ChatConversation)
            .filter(
                ChatConversation.id == conversation_id,
                ChatConversation.business_id == business_id,
            )
            .first()
        )

    def list_conversations(
        self,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ChatConversation], int]:
        q = self.db.query(ChatConversation).filter(
            ChatConversation.business_id == business_id,
            ChatConversation.user_id == user_id,
        )
        total = q.count()
        rows = q.order_by(ChatConversation.updated_at.desc()).offset(skip).limit(limit).all()
        return rows, total

    # ── Messages ─────────────────────────────────────────────────────────────

    def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        mentions_data: list | None = None,
        actions_data: list | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            mentions_data=mentions_data or [],
            actions_data=actions_data or [],
        )
        self.db.add(msg)
        self.db.flush()
        return msg

    def get_recent_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ChatMessage]:
        rows = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))

    def get_message_for_user(
        self,
        message_id: uuid.UUID,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChatMessage | None:
        """Scoped so a message from someone else's conversation is never
        found, not even to 404 with a distinguishing error - existence of
        another user's conversation is never leaked."""
        return (
            self.db.query(ChatMessage)
            .join(ChatConversation, ChatMessage.conversation_id == ChatConversation.id)
            .filter(
                ChatMessage.id == message_id,
                ChatConversation.business_id == business_id,
                ChatConversation.user_id == user_id,
            )
            .first()
        )

    def set_action_status(
        self,
        message: ChatMessage,
        action_id: str,
        expected_status: str,
        new_status: str,
        result: dict | None = None,
        error: str | None = None,
    ) -> dict | None:
        """Race-safe status transition: only succeeds if the action's current
        status equals expected_status (guards against double-click/double-tab
        confirm races). Returns the updated action dict, or None if the
        action id isn't found or the current status doesn't match."""
        actions = list(message.actions_data or [])
        for i, action in enumerate(actions):
            if action["id"] != action_id:
                continue
            if action["status"] != expected_status:
                return None
            updated = {
                **action,
                "status": new_status,
                "result": result,
                "error": error,
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
            actions[i] = updated
            message.actions_data = actions  # reassign whole list - SQLAlchemy detects the change
            self.db.flush()
            return updated
        return None
