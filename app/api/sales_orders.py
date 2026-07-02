"""Sales order API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.sales_order import OrderCreate, OrderListResponse, OrderResponse, OrderUpdate
from app.services.sales_order import SalesOrderService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/sales-orders",
    tags=["sales-orders"],
)


def _order_service(db: Session) -> SalesOrderService:
    return SalesOrderService(db, event_service=EventService(db))


@router.post("", response_model=OrderResponse)
def create_order(
    data: OrderCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create sales order. All roles allowed."""
    try:
        service = _order_service(db)
        order = service.create(current_user.business_id, current_user, data)
        db.commit()
        return OrderResponse.model_validate(order)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=OrderListResponse)
def list_orders(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List sales orders for the current business."""
    service = _order_service(db)
    orders, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get sales order by ID."""
    service = _order_service(db)
    order = service.get(current_user.business_id, current_user, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return OrderResponse.model_validate(order)


@router.patch("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: UUID,
    data: OrderUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update sales order. Owner/manager only."""
    try:
        service = _order_service(db)
        order = service.update(current_user.business_id, current_user, order_id, data)
        if not order:
            raise HTTPException(status_code=404, detail="Sales order not found")
        db.commit()
        return OrderResponse.model_validate(order)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
