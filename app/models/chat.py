"""Chat conversation and message models."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ChatConversation(BaseModel):
    __tablename__ = "chat_conversations"

    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(BaseModel):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mentions_data: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    actions_data: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )

    conversation: Mapped["ChatConversation"] = relationship(
        "ChatConversation", back_populates="messages"
    )
