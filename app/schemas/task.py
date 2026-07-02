"""Task request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskBase(BaseModel):
    """Shared task fields."""

    lead_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|in_progress|completed|overdue)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    """Create task request."""

    pass


class TaskUpdate(BaseModel):
    """Update task request."""

    lead_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|overdue)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    due_date: Optional[datetime] = None


class TaskResponse(TaskBase):
    """Task response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class TaskListResponse(BaseModel):
    """List of tasks response."""

    items: list[TaskResponse]
    total: int
    skip: int
    limit: int
