"""Customer API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.services.customer import CustomerService
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/customers",
    tags=["customers"],
)


def _customer_service(db: Session) -> CustomerService:
    """Create CustomerService with EventService wired for auto-event emission."""
    return CustomerService(db, event_service=EventService(db))


@router.post("", response_model=CustomerResponse)
def create_customer(
    data: CustomerCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create customer.
    
    🧨 RBAC: Only owner/manager can create.
    """
    try:
        service = _customer_service(db)
        customer = service.create(current_user.business_id, current_user, data)
        db.commit()
        return customer
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=CustomerListResponse)
def list_customers(
    skip: int = 0,
    limit: int = 100,
    name: str | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List customers.
    
    🧨 All roles can view customers in their business.
    """
    service = _customer_service(db)

    if name:
        customers, total = service.search(current_user.business_id, current_user, name, skip=skip, limit=limit)
    else:
        customers, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get customer by ID."""
    service = _customer_service(db)
    customer = service.get(current_user.business_id, current_user, customer_id)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update customer.
    
    🧨 RBAC: Only owner/manager can edit.
    """
    try:
        service = _customer_service(db)
        customer = service.update(current_user.business_id, current_user, customer_id, data)

        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        db.commit()
        return customer
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{customer_id}", response_model=dict)
def delete_customer(
    customer_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete customer.
    
    🧨 RBAC: Only owner can delete.
    """
    try:
        service = _customer_service(db)
        success = service.delete(current_user.business_id, current_user, customer_id)

        if not success:
            raise HTTPException(status_code=404, detail="Customer not found")

        db.commit()
        return {"message": "Customer deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
