"""Task repository - data access layer."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.task import Task, TaskAssignee
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Task repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Task)

    def set_assignees(self, task_id: UUID, user_ids: list[UUID], commit: bool = False) -> None:
        """Replace a task's full assignee set.

        Caller is responsible for the surrounding transaction boundary
        (default commit=False so this batches into a larger atomic write,
        matching the outbox pattern used elsewhere in this codebase).
        """
        self.db.query(TaskAssignee).filter(TaskAssignee.task_id == task_id).delete(synchronize_session=False)
        for user_id in dict.fromkeys(user_ids):  # de-dupe, preserve order
            self.db.add(TaskAssignee(task_id=task_id, user_id=user_id))
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def get_by_status(self, business_id: UUID, status: str, skip: int = 0, limit: int = 100) -> list[Task]:
        """Get tasks by status within business.
        
        🧨 CRITICAL: Filters by business_id to prevent data leaks.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.status == status,
        ).offset(skip).limit(limit).all()

    def count_by_status(self, business_id: UUID, status: str) -> int:
        """Count tasks by status within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.status == status,
        ).count()

    def _assigned_to_filter(self, assigned_to: UUID):
        """Match either the primary assignee or a co-assignee (task_assignees)."""
        co_assigned_task_ids = self.db.query(TaskAssignee.task_id).filter(TaskAssignee.user_id == assigned_to)
        return (Task.assigned_to == assigned_to) | Task.id.in_(co_assigned_task_ids)

    def get_assigned_to(self, business_id: UUID, assigned_to: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        """Get tasks assigned to user (primary or co-assignee) within business.

        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            self._assigned_to_filter(assigned_to),
        ).offset(skip).limit(limit).all()

    def count_assigned_to(self, business_id: UUID, assigned_to: UUID) -> int:
        """Count tasks assigned to user (primary or co-assignee) within business.

        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            self._assigned_to_filter(assigned_to),
        ).count()

    def get_by_lead(self, business_id: UUID, lead_id: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        """Get tasks for lead within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.lead_id == lead_id,
        ).offset(skip).limit(limit).all()

    def count_by_lead(self, business_id: UUID, lead_id: UUID) -> int:
        """Count tasks for lead within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.lead_id == lead_id,
        ).count()

    def get_overdue(self, business_id: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        """Get overdue tasks within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.due_date < datetime.now(tz=None),
            Task.status != "completed",
        ).offset(skip).limit(limit).all()

    def count_overdue(self, business_id: UUID) -> int:
        """Count overdue tasks within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.due_date < datetime.now(tz=None),
            Task.status != "completed",
        ).count()
