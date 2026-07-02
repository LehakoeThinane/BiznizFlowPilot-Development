"""Task repository - data access layer."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Task repository with business_id filtering.
    
    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Task)

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

    def get_assigned_to(self, business_id: UUID, assigned_to: UUID, skip: int = 0, limit: int = 100) -> list[Task]:
        """Get tasks assigned to user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.assigned_to == assigned_to,
        ).offset(skip).limit(limit).all()

    def count_assigned_to(self, business_id: UUID, assigned_to: UUID) -> int:
        """Count tasks assigned to user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Task).filter(
            Task.business_id == business_id,
            Task.assigned_to == assigned_to,
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
