"""Inventory API routes - locations and stock levels."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.inventory import (
    LocationCreate,
    LocationResponse,
    LocationUpdate,
    StockAdjustment,
    StockLevelResponse,
)
from app.services.inventory import InventoryService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["inventory"],
)


def _inventory_service(db: Session) -> InventoryService:
    return InventoryService(db, event_service=EventService(db))


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


@router.post("/locations", response_model=LocationResponse)
def create_location(
    data: LocationCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create inventory location. Owner/manager only."""
    try:
        service = _inventory_service(db)
        location = service.create_location(current_user.business_id, current_user, data)
        db.commit()
        return location
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations", response_model=list[LocationResponse])
def list_locations(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List inventory locations."""
    service = _inventory_service(db)
    locations, _ = service.list_locations(current_user.business_id, current_user, skip=skip, limit=limit)
    return [LocationResponse.model_validate(loc) for loc in locations]


@router.get("/locations/{location_id}", response_model=LocationResponse)
def get_location(
    location_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get inventory location by ID."""
    service = _inventory_service(db)
    location = service.get_location(current_user.business_id, current_user, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.patch("/locations/{location_id}", response_model=LocationResponse)
def update_location(
    location_id: UUID,
    data: LocationUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update inventory location. Owner/manager only."""
    try:
        service = _inventory_service(db)
        location = service.update_location(current_user.business_id, current_user, location_id, data)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        db.commit()
        return location
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/locations/{location_id}")
def delete_location(
    location_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete inventory location. Owner only."""
    try:
        service = _inventory_service(db)
        success = service.delete_location(current_user.business_id, current_user, location_id)
        if not success:
            raise HTTPException(status_code=404, detail="Location not found")
        db.commit()
        return {"message": "Location deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Stock Levels
# ---------------------------------------------------------------------------


@router.post("/stock/adjust", response_model=StockLevelResponse)
def adjust_stock(
    data: StockAdjustment,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Adjust stock quantity at a location. All roles allowed."""
    try:
        service = _inventory_service(db)
        stock = service.adjust_stock(current_user.business_id, current_user, data)
        db.commit()
        return StockLevelResponse.model_validate(stock)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
