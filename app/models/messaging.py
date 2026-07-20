"""Messaging model - direct (1:1) chat between colleagues in a business."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, Uuid
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
    """A single direct message within a Conversation.

    `message_type` selects which of the nullable reference columns below is
    populated: 'text' messages only use `content`; every other type carries
    an optional `content` caption plus the one reference matching its type.
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id       = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content         = Column(Text, nullable=True)

    message_type = Column(
        String(20), nullable=False, default="text", server_default="text",
        doc="text | document | image | video | audio | contact | poll | event | sticker",
    )

    attachment_id      = Column(Uuid, ForeignKey("message_attachments.id", ondelete="SET NULL"), nullable=True)
    shared_customer_id = Column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    shared_meeting_id  = Column(Uuid, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    poll_id            = Column(Uuid, ForeignKey("polls.id", ondelete="SET NULL"), nullable=True)
    sticker_key        = Column(String(50), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
    sender       = relationship("User", foreign_keys=[sender_id])
    attachment      = relationship("MessageAttachment")
    shared_customer = relationship("Customer")
    shared_meeting  = relationship("Meeting")
    poll            = relationship("Poll")

    def __repr__(self) -> str:
        return f"<Message id={self.id} conversation_id={self.conversation_id}>"
