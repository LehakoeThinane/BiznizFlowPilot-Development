"""Task model - work item entity."""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Uuid

from app.models.base import BaseModel


class Task(BaseModel):
    """Task entity.
    
    Represents a work item that needs to be done.
    Can be related to a lead or standalone.
    Belongs to a business.
    """

    __tablename__ = "tasks"

    SAFE_CONTEXT_FIELDS = {
        "id",
        "lead_id",
        "assigned_to",
        "title",
        "description",
        "status",
        "priority",
        "due_date",
        "completed_at",
    }

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )

    lead_id = Column(
        Uuid,
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Associated lead (optional)",
    )

    assigned_to = Column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="User responsible for this task",
    )

    title = Column(
        String(255),
        nullable=False,
        doc="Task title/description",
    )

    description = Column(
        Text,
        nullable=True,
        doc="Detailed task description",
    )

    status = Column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        doc="Task status: pending, in_progress, completed, overdue",
    )

    priority = Column(
        String(50),
        default="medium",
        nullable=False,
        index=True,
        doc="Task priority: low, medium, high, urgent",
    )

    due_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="When the task is due",
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the task was completed",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Task id={self.id} title='{self.title}' status='{self.status}'>"
