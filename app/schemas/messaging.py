"""Direct-message (colleague chat) schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    user_id: UUID


class OtherUser(BaseModel):
    id: UUID
    full_name: str
    email: str


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


class DirectMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    sender_id: UUID | None
    sender_name: str = ""
    content: str
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[DirectMessageOut]


class UnreadCountResponse(BaseModel):
    unread_count: int
