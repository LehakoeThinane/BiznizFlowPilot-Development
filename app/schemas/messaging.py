"""Direct-message (colleague chat) schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.user import PresenceOut


class ConversationCreate(BaseModel):
    user_id: UUID


class OtherUser(BaseModel):
    id: UUID
    full_name: str
    email: str
    avatar_url: str | None = None
    presence: PresenceOut


class LastMessagePreview(BaseModel):
    content: str
    created_at: datetime
    sender_id: UUID | None


class ConversationSummary(BaseModel):
    id: UUID
    other_user: OtherUser
    last_message: LastMessagePreview | None = None
    unread_count: int = 0


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


# ── Attachments ──────────────────────────────────────────────────────────

class MessageAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    content_type: str | None
    size_bytes: int
    kind: str
    download_url: str | None = None


class AttachmentDownloadResponse(BaseModel):
    url: str
    expires_in: int


# ── Contact sharing ──────────────────────────────────────────────────────

class ContactShareCreate(BaseModel):
    customer_id: UUID
    caption: str | None = Field(None, max_length=4000)


class SharedCustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None


# ── Event sharing / scheduling ────────────────────────────────────────────

class EventShareExisting(BaseModel):
    meeting_id: UUID
    caption: str | None = Field(None, max_length=4000)


class EventShareNew(BaseModel):
    title: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=2000)
    start_time: datetime
    end_time: datetime
    call_type: Literal["voice", "video"] = "video"
    participant_user_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_times(self) -> "EventShareNew":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SharedMeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    start_time: datetime
    end_time: datetime
    call_type: str
    status: str


# ── Stickers ───────────────────────────────────────────────────────────────

class StickerCreate(BaseModel):
    sticker_key: str = Field(..., max_length=50)


# ── Polls ─────────────────────────────────────────────────────────────────

class PollCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    options: list[str] = Field(..., min_length=2, max_length=10)
    allow_multiple: bool = False


class PollVoteRequest(BaseModel):
    option_ids: list[UUID] = Field(..., min_length=1)


class PollOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str
    vote_count: int = 0


class PollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    question: str
    allow_multiple: bool
    options: list[PollOptionOut]
    my_vote_option_ids: list[UUID] = []
    total_votes: int = 0


# ── Messages ─────────────────────────────────────────────────────────────

class DirectMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    sender_id: UUID | None
    sender_name: str = ""
    content: str | None
    message_type: str = "text"
    created_at: datetime

    attachment: MessageAttachmentOut | None = None
    shared_customer: SharedCustomerOut | None = None
    shared_meeting: SharedMeetingOut | None = None
    poll: PollOut | None = None
    sticker_key: str | None = None


class MessageListResponse(BaseModel):
    items: list[DirectMessageOut]


class UnreadCountResponse(BaseModel):
    unread_count: int
