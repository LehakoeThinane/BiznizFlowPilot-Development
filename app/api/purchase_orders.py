"""Purchase order API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.purchase_order import POCreate, POListResponse, POResponse, POUpdate
from app.services.purchase_order import PurchaseOrderService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/purchase-orders",
    tags=["purchase-orders"],
)


def _po_service(db: Session) -> PurchaseOrderService:
    return PurchaseOrderService(db, event_service=EventService(db))


@router.post("", response_model=POResponse)
def create_purchase_order(
    data: POCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create purchase order. Owner/manager only."""
    try:
        service = _po_service(db)
        po = service.create(current_user.business_id, current_user, data)
        db.commit()
        return POResponse.model_validate(po)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=POListResponse)
def list_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List purchase orders for the current business."""
    service = _po_service(db)
    pos, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    return POListResponse(
        items=[POResponse.model_validate(po) for po in pos],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{po_id}", response_model=POResponse)
def get_purchase_order(
    po_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get purchase order by ID."""
    service = _po_service(db)
    po = service.get(current_user.business_id, current_user, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return POResponse.model_validate(po)


@router.patch("/{po_id}", response_model=POResponse)
def update_purchase_order(
    po_id: UUID,
    data: POUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update purchase order. Owner/manager only."""
    try:
        service = _po_service(db)
        po = service.update(current_user.business_id, current_user, po_id, data)
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        db.commit()
        return POResponse.model_validate(po)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
