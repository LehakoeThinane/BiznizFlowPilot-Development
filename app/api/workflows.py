"""Workflow API routes.

Endpoints for workflow management and execution tracking.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowUpdate,
)
from app.services.workflow import WorkflowService

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new workflow.
    
    Only Owner and Manager roles can create workflows.
    Workflows define automation rules triggered by specific event types.
    """
    service = WorkflowService(db)
    try:
        return service.create_workflow(
            db=db,
            business_id=current_user.business_id,
            current_user=current_user,
            data=workflow_data,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=WorkflowListResponse)
def list_workflows(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """List all workflows for the business.
    
    All authenticated users can view workflows.
    """
    service = WorkflowService(db)
    workflows = service.list_workflows(
        db=db,
        business_id=current_user.business_id,
        current_user=current_user,
    )
    return {"total": len(workflows), "workflows": workflows}


@router.get("/{workflow_id:uuid}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get workflow by ID.
    
    Returns workflow definition with all configured actions.
    """
    service = WorkflowService(db)
    workflow = service.get_workflow(
        db=db,
        business_id=current_user.business_id,
        current_user=current_user,
        workflow_id=workflow_id,
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/{workflow_id:uuid}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: UUID,
    workflow_data: WorkflowUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Update workflow.
    
    Only Owner and Manager can update workflows.
    Note: This updates top-level fields only. To modify actions, delete and recreate workflow.
    """
    service = WorkflowService(db)
    try:
        workflow = service.update_workflow(
            db=db,
            business_id=current_user.business_id,
            current_user=current_user,
            workflow_id=workflow_id,
            data=workflow_data,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.delete("/{workflow_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Delete workflow and all associated actions.
    
    Only Owner and Manager can delete workflows.
    """
    service = WorkflowService(db)
    try:
        success = service.delete_workflow(
            db=db,
            business_id=current_user.business_id,
            current_user=current_user,
            workflow_id=workflow_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if not success:
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.patch("/{workflow_id:uuid}/toggle", response_model=WorkflowResponse)
def toggle_workflow(
    workflow_id: UUID,
    enabled: bool,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Enable or disable workflow.
    
    Only Owner and Manager can toggle workflows.
    Disabled workflows will not trigger on events.
    """
    service = WorkflowService(db)
    try:
        workflow = service.toggle_workflow(
            db=db,
            business_id=current_user.business_id,
            current_user=current_user,
            workflow_id=workflow_id,
            enabled=enabled,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.get("/{workflow_id:uuid}/runs", response_model=WorkflowRunListResponse)
def get_workflow_runs(
    workflow_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get execution history for a workflow.
    
    Shows all times this workflow has been executed with results and status.
    """
    service = WorkflowService(db)
    workflow = service.get_workflow(
        db=db,
        business_id=current_user.business_id,
        current_user=current_user,
        workflow_id=workflow_id,
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    runs = service.run_repository.get_by_workflow(
        db=db, business_id=current_user.business_id, workflow_id=workflow_id
    )
    return {"total": len(runs), "runs": runs}


@router.get("/runs/{run_id:uuid}", response_model=WorkflowRunResponse)
def get_workflow_run(
    run_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get execution details for a specific workflow run.
    
    Returns complete run data including status, results, and any errors.
    """
    service = WorkflowService(db)
    run = service.get_run(
        db=db,
        business_id=current_user.business_id,
        run_id=run_id,
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.get("/runs", response_model=WorkflowRunListResponse)
def list_workflow_runs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """List all workflow runs for the business.
    
    Shows execution history for all workflows.
    """
    service = WorkflowService(db)
    runs = service.list_runs(
        db=db,
        business_id=current_user.business_id,
        current_user=current_user,
    )
    return {"total": len(runs), "runs": runs}
