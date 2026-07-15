"""Task model - work item entity."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Task(BaseModel):
    """Task entity.

    Represents a work item that needs to be done.
    Can be related to a lead or standalone.
    Belongs to a business.
    """

    __tablename__ = "tasks"

    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        doc="Optimistic-concurrency guard - SQLAlchemy increments this on every "
            "UPDATE and includes it in the WHERE clause; a stale write raises "
            "StaleDataError instead of silently overwriting a concurrent change.",
    )

    __mapper_args__ = {"version_id_col": version}

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

    source_workflow_action_id = Column(
        Uuid,
        ForeignKey("workflow_actions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
        doc="Workflow action that created this task, if any. The unique "
            "constraint gives CreateTaskHandler real idempotency: if a retry "
            "runs after an earlier attempt already succeeded, the second "
            "INSERT hits this constraint instead of silently duplicating "
            "the task.",
    )

    assignees = relationship("TaskAssignee", back_populates="task", cascade="all, delete-orphan")

    @property
    def assignee_ids(self) -> list:
        """Full assignee set (primary `assigned_to` included, if also in the join table)."""
        return [a.user_id for a in self.assignees]

    def __repr__(self) -> str:
        """String representation."""
        return f"<Task id={self.id} title='{self.title}' status='{self.status}'>"


class TaskAssignee(BaseModel):
    """A user assigned to a Task, in addition to the primary `assigned_to`.

    Enables multi-person assignment: `assigned_to` remains the single
    "primary" assignee used by existing staff-visibility/filtering logic,
    while this table holds the full assignee set (primary included).
    """

    __tablename__ = "task_assignees"
    __table_args__ = (
        Index("ix_task_assignees_task_user", "task_id", "user_id", unique=True),
    )

    task_id = Column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    task = relationship("Task", back_populates="assignees")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<TaskAssignee task_id={self.task_id} user_id={self.user_id}>"
