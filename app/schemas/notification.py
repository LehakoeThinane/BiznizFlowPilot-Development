"""Notification schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    type: str
    title: str
    message: str
    is_read: bool
    action_url: str | None
    related_type: str | None
    related_id: UUID | None
    created_at: datetime


class NotificationCount(BaseModel):
    unread: int
    total: int


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
