"""Lead API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.lead import LeadCreate, LeadListResponse, LeadResponse, LeadUpdate
from app.services.event import EventService
from app.services.lead import LeadService

router = APIRouter(
    prefix="/api/v1/leads",
    tags=["leads"],
)


def _lead_service(db: Session) -> LeadService:
    """Create LeadService with EventService wired for auto-event emission."""
    return LeadService(db, event_service=EventService(db))


@router.post("", response_model=LeadResponse)
def create_lead(
    data: LeadCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create lead.
    
    🧨 RBAC: Only owner/manager can create.
    """
    try:
        service = _lead_service(db)
        lead = service.create(current_user.business_id, current_user, data)
        db.commit()
        return lead
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=LeadListResponse)
def list_leads(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List leads.
    
    🧨 RBAC: Owner/Manager see all. Staff see assigned to them.
    """
    service = _lead_service(db)

    if status:
        leads, total = service.list_by_status(current_user.business_id, current_user, status, skip=skip, limit=limit)
    else:
        leads, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)

    return LeadListResponse(
        items=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get lead by ID.
    
    🧨 RBAC: All roles can view leads in their business.
    """
    service = _lead_service(db)
    lead = service.get(current_user.business_id, current_user, lead_id)

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: UUID,
    data: LeadUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update lead.
    
    🧨 RBAC: Owner/Manager can edit all. Staff can only update their own.
    """
    try:
        service = _lead_service(db)
        lead = service.update(current_user.business_id, current_user, lead_id, data)

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        db.commit()
        return lead
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{lead_id}/assign/{assigned_to}", response_model=LeadResponse)
def assign_lead(
    lead_id: UUID,
    assigned_to: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Assign lead to user.
    
    🧨 RBAC: Only owner/manager can assign.
    """
    try:
        service = _lead_service(db)
        lead = service.assign(current_user.business_id, current_user, lead_id, assigned_to)

        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        db.commit()
        return lead
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{lead_id}", response_model=dict)
def delete_lead(
    lead_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete lead.
    
    🧨 RBAC: Only owner can delete.
    """
    try:
        service = _lead_service(db)
        success = service.delete(current_user.business_id, current_user, lead_id)

        if not success:
            raise HTTPException(status_code=404, detail="Lead not found")

        db.commit()
        return {"message": "Lead deleted successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
