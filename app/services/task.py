"""Task service - business logic with auto-event emission."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


class TaskService:
    """Task service with RBAC and task management.
    
    🧨 RBAC: Owner/Manager can create/assign. Staff can view own and complete.
    State transitions: pending → in_progress → completed
    Overdue is a computed status based on due_date.
    
    Auto-emits events on create/update/complete/delete when event_service is provided.
    """

    # Valid state transitions for tasks
    VALID_TRANSITIONS = {
        "pending": ["in_progress", "completed"],
        "in_progress": ["completed", "pending"],
        "completed": [],
        "overdue": ["in_progress", "completed"],
    }

    def __init__(self, db: Session, event_service=None):
        """Initialize service.
        
        Args:
            db: SQLAlchemy session
            event_service: Optional EventService for auto-event emission.
                           When None, no events are emitted (backward compatible).
        """
        self.db = db
        self.repo = TaskRepository(db)
        self._event_service = event_service

    def _emit_event(
        self,
        event_type: EventType,
        business_id: UUID,
        entity_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Emit an event if event_service is available. Never raises."""
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id,
                event_type=event_type,
                entity_type="task",
                entity_id=entity_id,
                actor_id=actor_id,
                description=description,
                data=data,
            )
        except Exception:
            logger.warning(
                "Failed to emit %s event for task %s",
                event_type.value,
                entity_id,
                exc_info=True,
            )

    def create(self, business_id: UUID, current_user: CurrentUser, data: TaskCreate) -> Task:
        """Create task.
        
        🧨 RBAC: Only owner/manager can create.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can create tasks")

        task = self.repo.create(business_id=business_id, **data.model_dump())

        self._emit_event(
            event_type=EventType.TASK_CREATED,
            business_id=business_id,
            entity_id=task.id,
            actor_id=current_user.user_id,
            description=f"Task created: '{task.title}'",
            data={
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            },
        )

        return task

    def get(self, business_id: UUID, current_user: CurrentUser, task_id: UUID) -> Task | None:
        """Get task by ID.
        
        🧨 RBAC: All roles can view tasks in their business, but staff only see assigned to them.
        """
        task = self.repo.get(business_id=business_id, entity_id=task_id)
        if not task:
            return None

        # Staff can only view tasks assigned to them
        if current_user.role == "staff" and task.assigned_to != current_user.id:
            raise ValueError("Permission denied: Staff can only view their own tasks")

        return task

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Task], int]:
        """List tasks.
        
        🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
        """
        if current_user.role in ["owner", "manager"]:
            tasks = self.repo.list(business_id=business_id, skip=skip, limit=limit)
            total = self.repo.count(business_id=business_id)
        else:
            # Staff only sees tasks assigned to them
            tasks = self.repo.get_assigned_to(business_id=business_id, assigned_to=current_user.id, skip=skip, limit=limit)
            total = self.repo.count_assigned_to(business_id=business_id, assigned_to=current_user.id)

        return tasks, total

    def list_by_status(self, business_id: UUID, current_user: CurrentUser, status: str, skip: int = 0, limit: int = 100) -> tuple[list[Task], int]:
        """List tasks by status.
        
        🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
        """
        if current_user.role in ["owner", "manager"]:
            tasks = self.repo.get_by_status(business_id=business_id, status=status, skip=skip, limit=limit)
            total = self.repo.count_by_status(business_id=business_id, status=status)
        else:
            # Staff only sees own tasks
            all_tasks = self.repo.get_assigned_to(business_id=business_id, assigned_to=current_user.id)
            tasks = [t for t in all_tasks if t.status == status][skip:skip+limit]
            total = len([t for t in all_tasks if t.status == status])

        return tasks, total

    def list_overdue(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Task], int]:
        """List overdue tasks.
        
        🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
        """
        if current_user.role in ["owner", "manager"]:
            tasks = self.repo.get_overdue(business_id=business_id, skip=skip, limit=limit)
            total = self.repo.count_overdue(business_id=business_id)
        else:
            # Staff only sees own overdue tasks
            all_tasks = self.repo.get_assigned_to(business_id=business_id, assigned_to=current_user.id)
            overdue = [t for t in all_tasks if t.due_date and t.due_date < datetime.now(timezone.utc) and t.status != "completed"]
            tasks = overdue[skip:skip+limit]
            total = len(overdue)

        return tasks, total

    def update(self, business_id: UUID, current_user: CurrentUser, task_id: UUID, data: TaskUpdate) -> Task | None:
        """Update task.
        
        🧨 RBAC: Owner/Manager can edit all. Staff can only update their own.
        """
        task = self.repo.get(business_id=business_id, entity_id=task_id)
        if not task:
            return None

        # Staff can only update their own tasks
        if current_user.role == "staff" and task.assigned_to != current_user.id:
            raise ValueError("Permission denied: Staff can only update their own tasks")

        old_status = task.status

        # Validate state transition if status is being updated
        if data.status is not None and data.status != task.status:
            if not self._is_valid_transition(task.status, data.status):
                raise ValueError(f"Invalid state transition: {task.status} → {data.status}")

        update_data = data.model_dump(exclude_unset=True)

        # Mark completed_at when status changes to completed
        if data.status == "completed":
            update_data["completed_at"] = datetime.now(timezone.utc)

        updated_task = self.repo.update(business_id=business_id, entity_id=task_id, **update_data)

        if updated_task:
            # Emit the most specific event type
            if data.status == "completed" and old_status != "completed":
                self._emit_event(
                    event_type=EventType.TASK_COMPLETED,
                    business_id=business_id,
                    entity_id=task_id,
                    actor_id=current_user.user_id,
                    description=f"Task completed: '{updated_task.title}'",
                    data={"title": updated_task.title, "old_status": old_status},
                )
            elif data.status is not None and data.status != old_status:
                self._emit_event(
                    event_type=EventType.TASK_UPDATED,
                    business_id=business_id,
                    entity_id=task_id,
                    actor_id=current_user.user_id,
                    description=f"Task status changed: {old_status} → {data.status}",
                    data={"old_status": old_status, "new_status": data.status},
                )
            else:
                self._emit_event(
                    event_type=EventType.TASK_UPDATED,
                    business_id=business_id,
                    entity_id=task_id,
                    actor_id=current_user.user_id,
                    description="Task updated",
                    data={"updated_fields": list(update_data.keys())},
                )

        return updated_task

    def assign(self, business_id: UUID, current_user: CurrentUser, task_id: UUID, assigned_to: UUID) -> Task | None:
        """Assign task to user.
        
        🧨 RBAC: Only owner/manager can assign.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can assign tasks")

        task = self.repo.get(business_id=business_id, entity_id=task_id)
        if not task:
            return None

        old_assigned = task.assigned_to
        updated_task = self.repo.update(business_id=business_id, entity_id=task_id, assigned_to=assigned_to)

        if updated_task:
            self._emit_event(
                event_type=EventType.TASK_ASSIGNED,
                business_id=business_id,
                entity_id=task_id,
                actor_id=current_user.user_id,
                description=f"Task '{updated_task.title}' assigned to {assigned_to}",
                data={
                    "title": updated_task.title,
                    "old_assigned_to": str(old_assigned) if old_assigned else None,
                    "new_assigned_to": str(assigned_to),
                },
            )

        return updated_task

    def delete(self, business_id: UUID, current_user: CurrentUser, task_id: UUID) -> bool:
        """Delete task.
        
        🧨 RBAC: Only owner can permanently delete.
        """
        if current_user.role != "owner":
            raise ValueError("Permission denied: Only owner can delete tasks")

        task = self.repo.get(business_id=business_id, entity_id=task_id)
        if not task:
            return False

        # Emit event before deletion (entity still exists for context)
        self._emit_event(
            event_type=EventType.TASK_DELETED,
            business_id=business_id,
            entity_id=task_id,
            actor_id=current_user.user_id,
            description=f"Task deleted: '{task.title}'",
            data={"title": task.title, "status": task.status},
        )

        self.repo.delete(business_id=business_id, entity_id=task_id)
        return True

    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Check if state transition is valid."""
        return new_status in TaskService.VALID_TRANSITIONS.get(current_status, [])
