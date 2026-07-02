"""Task API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.event import EventService
from app.services.task import TaskService

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
)


def _task_service(db: Session) -> TaskService:
    """Create TaskService with EventService wired for auto-event emission."""
    return TaskService(db, event_service=EventService(db))


@router.post("", response_model=TaskResponse)
def create_task(
    data: TaskCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create task.
    
    🧨 RBAC: Only owner/manager can create.
    """
    try:
        service = _task_service(db)
        task = service.create(current_user.business_id, current_user, data)
        db.commit()
        return task
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TaskListResponse)
def list_tasks(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    overdue_only: bool = False,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List tasks.
    
    🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
    """
    service = _task_service(db)

    if overdue_only:
        tasks, total = service.list_overdue(current_user.business_id, current_user, skip=skip, limit=limit)
    elif status:
        tasks, total = service.list_by_status(current_user.business_id, current_user, status, skip=skip, limit=limit)
    else:
        tasks, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)

    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get task by ID.
    
    🧨 RBAC: All roles can view tasks in their business.
    """
    try:
        service = _task_service(db)
        task = service.get(current_user.business_id, current_user, task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    data: TaskUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update task.
    
    🧨 RBAC: Owner/Manager can edit all. Staff can only update their own.
    """
    try:
        service = _task_service(db)
        task = service.update(current_user.business_id, current_user, task_id, data)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        db.commit()
        return task
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/assign/{assigned_to}", response_model=TaskResponse)
def assign_task(
    task_id: UUID,
    assigned_to: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Assign task to user.
    
    🧨 RBAC: Only owner/manager can assign.
    """
    try:
        service = _task_service(db)
        task = service.assign(current_user.business_id, current_user, task_id, assigned_to)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        db.commit()
        return task
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}", response_model=dict)
def delete_task(
    task_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete task.
    
    🧨 RBAC: Only owner can delete.
    """
    try:
        service = _task_service(db)
        success = service.delete(current_user.business_id, current_user, task_id)

        if not success:
            raise HTTPException(status_code=404, detail="Task not found")

        db.commit()
        return {"message": "Task deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
