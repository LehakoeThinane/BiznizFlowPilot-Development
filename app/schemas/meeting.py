"""Meeting scheduling & Agora call schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Meetings ───────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=2000)
    start_time: datetime
    end_time: datetime
    call_type: Literal["voice", "video"] = "video"
    participant_user_ids: list[UUID] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_times(self) -> "MeetingCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class MeetingUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    start_time: datetime | None = None
    end_time: datetime | None = None
    call_type: Literal["voice", "video"] | None = None
    status: Literal["scheduled", "cancelled"] | None = None


class MeetingRespondRequest(BaseModel):
    response_status: Literal["accepted", "declined"]


class MeetingParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    full_name: str = ""
    email: str | None = None
    response_status: str
    joined_at: datetime | None


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    organizer_id: UUID | None
    organizer_name: str = ""
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    call_type: str
    status: str
    created_at: datetime
    participants: list[MeetingParticipantOut] = []


class MeetingListResponse(BaseModel):
    items: list[MeetingOut]
    total: int
    skip: int
    limit: int


# ── Agora ──────────────────────────────────────────────────────────────────

class AgoraJoinResponse(BaseModel):
    agora_app_id: str
    channel_name: str
    token: str
    uid: int
    expires_at: datetime
