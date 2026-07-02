"""Meeting model - scheduled calls between users, with Agora-backed voice/video."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Meeting(BaseModel):
    """A scheduled voice/video meeting between users within a business."""

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_biz_start", "business_id", "start_time"),
        Index("ix_meetings_biz_status", "business_id", "status"),
    )

    business_id  = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    organizer_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    title       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time   = Column(DateTime(timezone=True), nullable=False)

    call_type = Column(String(20), nullable=False, server_default="video", doc="voice | video")
    status    = Column(String(20), nullable=False, server_default="scheduled", doc="scheduled | in_progress | completed | cancelled")

    agora_channel_name = Column(String(100), nullable=False, unique=True)

    organizer    = relationship("User", foreign_keys=[organizer_id])
    participants = relationship("MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title='{self.title}' status='{self.status}'>"


class MeetingParticipant(BaseModel):
    """A user invited to (or organizing) a Meeting."""

    __tablename__ = "meeting_participants"
    __table_args__ = (
        Index("ix_meeting_participants_user", "user_id"),
    )

    meeting_id = Column(Uuid, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    response_status = Column(String(20), nullable=False, server_default="pending", doc="pending | accepted | declined")
    joined_at        = Column(DateTime(timezone=True), nullable=True)

    meeting = relationship("Meeting", back_populates="participants")
    user    = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<MeetingParticipant meeting_id={self.meeting_id} user_id={self.user_id} status='{self.response_status}'>"
