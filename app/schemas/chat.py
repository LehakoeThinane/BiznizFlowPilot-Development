"""Pydantic schemas for the chat API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    mentions_data: list
    actions_data: list
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatConversationOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatConversationDetail(ChatConversationOut):
    messages: list[ChatMessageOut]


class SendMessageRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None


class SendMessageResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    resolved_mentions: list[dict]
    user_message_id: uuid.UUID
    assistant_message_id: uuid.UUID


class MentionSearchResult(BaseModel):
    id: str
    label: str
    sub: str
