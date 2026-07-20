"""Poll models - a poll sent in a chat message, with options and votes."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Poll(BaseModel):
    """A poll attached to a direct-message conversation."""

    __tablename__ = "polls"

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    question = Column(String(500), nullable=False)
    allow_multiple = Column(Boolean, nullable=False, default=False, server_default="false")

    options = relationship("PollOption", back_populates="poll", cascade="all, delete-orphan", order_by="PollOption.position")

    def __repr__(self) -> str:
        return f"<Poll id={self.id} question='{self.question}'>"


class PollOption(BaseModel):
    """A single selectable option on a Poll."""

    __tablename__ = "poll_options"

    poll_id = Column(Uuid, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    position = Column(Integer, nullable=False, default=0)

    poll = relationship("Poll", back_populates="options")
    votes = relationship("PollVote", back_populates="option", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PollOption id={self.id} text='{self.text}'>"


class PollVote(BaseModel):
    """A user's vote for one option of a Poll."""

    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("option_id", "user_id", name="uq_poll_vote_option_user"),
    )

    poll_id = Column(Uuid, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(Uuid, ForeignKey("poll_options.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    option = relationship("PollOption", back_populates="votes")

    def __repr__(self) -> str:
        return f"<PollVote poll_id={self.poll_id} option_id={self.option_id} user_id={self.user_id}>"
