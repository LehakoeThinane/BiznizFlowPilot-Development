"""Supplier API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.supplier import SupplierCreate, SupplierListResponse, SupplierResponse, SupplierUpdate
from app.services.supplier import SupplierService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/suppliers",
    tags=["suppliers"],
)


def _supplier_service(db: Session) -> SupplierService:
    return SupplierService(db, event_service=EventService(db))


@router.post("", response_model=SupplierResponse)
def create_supplier(
    data: SupplierCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create supplier. Owner/manager only."""
    try:
        service = _supplier_service(db)
        supplier = service.create(current_user.business_id, current_user, data)
        db.commit()
        return supplier
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List suppliers for the current business."""
    service = _supplier_service(db)
    suppliers, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in suppliers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get supplier by ID."""
    service = _supplier_service(db)
    supplier = service.get(current_user.business_id, current_user, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update supplier. Owner/manager only."""
    try:
        service = _supplier_service(db)
        supplier = service.update(current_user.business_id, current_user, supplier_id, data)
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        db.commit()
        return supplier
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete supplier. Owner only."""
    try:
        service = _supplier_service(db)
        success = service.delete(current_user.business_id, current_user, supplier_id)
        if not success:
            raise HTTPException(status_code=404, detail="Supplier not found")
        db.commit()
        return {"message": "Supplier deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
