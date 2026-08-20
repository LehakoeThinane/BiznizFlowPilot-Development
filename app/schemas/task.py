"""Task request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    assignee_ids: Optional[list[UUID]] = Field(
        None, description="Full set of assignees. When provided, assigned_to is derived as the first entry."
    )


class TaskUpdate(BaseModel):
    """Update task request."""

    lead_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    assignee_ids: Optional[list[UUID]] = Field(
        None, description="Replaces the full assignee set when provided (empty list clears all assignees)."
    )
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
    assignee_ids: list[UUID] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _apply_overdue(self) -> "TaskResponse":
        """The DB only ever stores pending/in_progress/completed - nothing
        writes "overdue" on the row itself. It's a read-time fact derived
        from due_date, recomputed here so every response (board, list,
        filters, get-by-id) agrees without a scheduled job to keep in sync.

        due_date arrives tz-aware from Postgres but naive from SQLite (used
        in tests) - compare against a "now" of matching awareness either way.
        """
        if self.status == "completed" or not self.due_date:
            return self
        now = datetime.now(self.due_date.tzinfo) if self.due_date.tzinfo else datetime.now(tz=None)
        if self.due_date < now:
            self.status = "overdue"
        return self


class TaskListResponse(BaseModel):
    """List of tasks response."""

    items: list[TaskResponse]
    total: int
    skip: int
    limit: int
