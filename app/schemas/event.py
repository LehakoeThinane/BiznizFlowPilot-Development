"""Event request/response schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import EventStatus, EventType


class EventCreate(BaseModel):
    """Create event request."""

    event_type: EventType
    entity_type: str = Field(..., min_length=1, max_length=50)
    entity_id: UUID
    actor_id: Optional[UUID] = None
    description: Optional[str] = Field(None, max_length=500)
    data: Optional[dict[str, Any]] = None


class EventResponse(BaseModel):
    """Event response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    actor_id: Optional[UUID] = None
    event_type: EventType
    entity_type: str
    entity_id: UUID
    description: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    status: EventStatus
    locked_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    processed: bool
    created_at: datetime
    updated_at: datetime

class EventListResponse(BaseModel):
    """List of events response."""

    items: list[EventResponse]
    total: int
    skip: int
    limit: int


class EventAuditTrailResponse(BaseModel):
    """Audit trail for an entity."""

    entity_type: str
    entity_id: UUID
    event_count: int
    skip: int
    limit: int
    events: list[EventResponse]
