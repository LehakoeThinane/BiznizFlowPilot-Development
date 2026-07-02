"""Product API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.services.product import ProductService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
)


def _product_service(db: Session) -> ProductService:
    return ProductService(db, event_service=EventService(db))


@router.post("", response_model=ProductResponse)
def create_product(
    data: ProductCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create product. Owner/manager only."""
    try:
        service = _product_service(db)
        product = service.create(current_user.business_id, current_user, data)
        db.commit()
        return product
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ProductListResponse)
def list_products(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List products for the current business."""
    service = _product_service(db)
    products, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get product by ID."""
    service = _product_service(db)
    product = service.get(current_user.business_id, current_user, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update product. Owner/manager only."""
    try:
        service = _product_service(db)
        product = service.update(current_user.business_id, current_user, product_id, data)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        db.commit()
        return product
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{product_id}")
def delete_product(
    product_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete product. Owner only."""
    try:
        service = _product_service(db)
        success = service.delete(current_user.business_id, current_user, product_id)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        db.commit()
        return {"message": "Product deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
