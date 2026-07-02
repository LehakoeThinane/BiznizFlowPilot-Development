"""Workflow definition CRUD routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import EventType
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionResponse,
    WorkflowDefinitionUpdate,
)
from app.services.workflow_definition import WorkflowDefinitionService

router = APIRouter(
    prefix="/api/v1/workflow-definitions",
    tags=["workflow-definitions"],
)


@router.post("", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_definition(
    data: WorkflowDefinitionCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a workflow definition."""
    service = WorkflowDefinitionService(db)
    try:
        return service.create(
            business_id=current_user.business_id,
            current_user=current_user,
            data=data,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=WorkflowDefinitionListResponse)
def list_workflow_definitions(
    skip: int = 0,
    limit: int = 100,
    event_type: EventType | None = None,
    is_active: bool | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List workflow definitions for the current tenant."""
    safe_limit = max(1, min(limit, settings.max_page_size))
    service = WorkflowDefinitionService(db)
    items, total = service.list(
        business_id=current_user.business_id,
        event_type=event_type,
        is_active=is_active,
        skip=skip,
        limit=safe_limit,
    )
    return WorkflowDefinitionListResponse(
        items=[WorkflowDefinitionResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=safe_limit,
    )


@router.get("/{definition_id}", response_model=WorkflowDefinitionResponse)
def get_workflow_definition(
    definition_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get one workflow definition by ID."""
    service = WorkflowDefinitionService(db)
    definition = service.get(
        business_id=current_user.business_id,
        definition_id=definition_id,
    )
    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return definition


@router.patch("/{definition_id}", response_model=WorkflowDefinitionResponse)
def update_workflow_definition(
    definition_id: UUID,
    data: WorkflowDefinitionUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Patch workflow definition fields."""
    service = WorkflowDefinitionService(db)
    try:
        definition = service.update(
            business_id=current_user.business_id,
            current_user=current_user,
            definition_id=definition_id,
            data=data,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return definition


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow_definition(
    definition_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Soft delete a workflow definition."""
    service = WorkflowDefinitionService(db)
    try:
        deleted = service.soft_delete(
            business_id=current_user.business_id,
            current_user=current_user,
            definition_id=definition_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
