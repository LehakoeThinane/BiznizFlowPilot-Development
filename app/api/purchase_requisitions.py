"""Purchase requisition API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.purchase_order import POResponse
from app.schemas.purchase_requisition import PRCreate, PRListResponse, PRResponse, PRStatusUpdate
from app.services.event import EventService
from app.services.purchase_requisition import PurchaseRequisitionService

router = APIRouter(
    prefix="/api/v1/purchase-requisitions",
    tags=["purchase-requisitions"],
    dependencies=[Depends(require_feature("purchase_orders"))],
)


def _pr_service(db: Session) -> PurchaseRequisitionService:
    return PurchaseRequisitionService(db, event_service=EventService(db))


@router.post("", response_model=PRResponse)
def create_purchase_requisition(
    data: PRCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Submit a purchase requisition. Any active business role may request."""
    try:
        service = _pr_service(db)
        pr = service.create(current_user.business_id, current_user, data)
        return PRResponse.model_validate(pr)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=PRListResponse)
def list_purchase_requisitions(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List purchase requisitions for the current business."""
    service = _pr_service(db)
    prs, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    return PRListResponse(
        items=[PRResponse.model_validate(pr) for pr in prs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{pr_id}", response_model=PRResponse)
def get_purchase_requisition(
    pr_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get purchase requisition by ID."""
    service = _pr_service(db)
    pr = service.get(current_user.business_id, current_user, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase requisition not found")
    return PRResponse.model_validate(pr)


@router.patch("/{pr_id}/status", response_model=PRResponse)
def update_purchase_requisition_status(
    pr_id: UUID,
    data: PRStatusUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Approve, reject, or cancel a pending purchase requisition. Owner/manager only."""
    try:
        service = _pr_service(db)
        pr = service.update_status(current_user.business_id, current_user, pr_id, data)
        if not pr:
            raise HTTPException(status_code=404, detail="Purchase requisition not found")
        return PRResponse.model_validate(pr)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pr_id}/convert", response_model=POResponse)
def convert_purchase_requisition(
    pr_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Convert an approved purchase requisition into a real purchase order. Owner/manager only."""
    try:
        service = _pr_service(db)
        result = service.convert_to_purchase_order(current_user.business_id, current_user, pr_id)
        if not result:
            raise HTTPException(status_code=404, detail="Purchase requisition not found")
        _pr, po = result
        return POResponse.model_validate(po)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
