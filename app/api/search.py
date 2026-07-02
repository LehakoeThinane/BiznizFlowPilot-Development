"""Global search — ILIKE across customers, products, invoices, tasks."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.task import Task
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/api/v1/search", tags=["search"])

_LIMIT = 5  # results per category


@router.get("")
def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Search customers, products, invoices and tasks for the current business."""
    biz = current_user.business_id
    pattern = f"%{q}%"

    customers = (
        db.query(Customer)
        .filter(
            Customer.business_id == biz,
            (Customer.name.ilike(pattern))
            | (Customer.email.ilike(pattern))
            | (Customer.company.ilike(pattern)),
        )
        .limit(_LIMIT)
        .all()
    )

    products = (
        db.query(Product)
        .filter(
            Product.business_id == biz,
            Product.is_active.is_(True),
            (Product.name.ilike(pattern)) | (Product.sku.ilike(pattern)),
        )
        .limit(_LIMIT)
        .all()
    )

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.business_id == biz,
            Invoice.invoice_number.ilike(pattern),
        )
        .limit(_LIMIT)
        .all()
    )

    tasks = (
        db.query(Task)
        .filter(
            Task.business_id == biz,
            (Task.title.ilike(pattern)) | (Task.description.ilike(pattern)),
        )
        .limit(_LIMIT)
        .all()
    )

    is_privileged = current_user.role in ("owner", "manager")

    return {
        "query": q,
        "results": {
            "customers": [
                {"id": str(c.id), "label": c.name, "sub": c.email or c.company or "", "href": "/leads"}
                for c in customers
            ],
            "products": [
                {"id": str(p.id), "label": p.name, "sub": p.sku or "", "href": "/inventory"}
                for p in products
            ],
            # Invoices contain financial data — restricted to owner/manager
            "invoices": [
                {
                    "id": str(i.id),
                    "label": i.invoice_number,
                    "sub": f"R {float(i.total_amount):,.2f} · {i.status}",
                    "href": "/invoices",
                }
                for i in invoices
            ] if is_privileged else [],
            "tasks": [
                {"id": str(t.id), "label": t.title, "sub": t.status, "href": "/tasks"}
                for t in tasks
            ],
        },
    }
