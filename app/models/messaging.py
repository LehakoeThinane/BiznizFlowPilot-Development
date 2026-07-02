"""Messaging model - direct (1:1) chat between colleagues in a business."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Conversation(BaseModel):
    """A direct-message conversation between two users of the same business."""

    __tablename__ = "conversations"

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    participants = relationship("ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan")
    messages     = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id}>"


class ConversationParticipant(BaseModel):
    """A user's membership in a Conversation, tracking their read position."""

    __tablename__ = "conversation_participants"
    __table_args__ = (
        Index("ix_conversation_participants_user", "user_id"),
    )

    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id         = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_at    = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="participants")
    user         = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<ConversationParticipant conversation_id={self.conversation_id} user_id={self.user_id}>"


class Message(BaseModel):
    """A single direct message within a Conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id       = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content         = Column(Text, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    sender       = relationship("User", foreign_keys=[sender_id])

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id}>"
