"""MM Nexus website chat widget schemas - public (no auth) request/response
shapes for app/api/website_chat.py."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WidgetSendRequest(BaseModel):
    session_token: str | None = None
    text: str = Field(..., min_length=1, max_length=4000)


class WidgetMessageOut(BaseModel):
    id: UUID
    content: str | None
    from_: Literal["visitor", "ai", "staff"] = Field(..., alias="from")
    created_at: datetime

    model_config = {"populate_by_name": True}


class WidgetSendResponse(BaseModel):
    session_token: str
    messages: list[WidgetMessageOut]


class WidgetPollResponse(BaseModel):
    messages: list[WidgetMessageOut]
