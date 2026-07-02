"""Repository for chat conversations and messages."""

from __future__ import annotations

import uuid

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
