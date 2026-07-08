"""Finance API — expense categories, expenses, P&L summary."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Annotated
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES
from app.dependencies import get_current_user
from app.models.finance import Expense, ExpenseCategory
from app.models.sales_order import SalesOrder
from app.schemas.auth import CurrentUser
from app.schemas.finance import (
    CategoryTotal,
    ExpenseCategoryCreate,
    ExpenseCategoryOut,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseOut,
    ExpenseUpdate,
    FinanceSummary,
)
from app.services.event import EventService

router = APIRouter(prefix="/api/v1/finance", tags=["finance"], dependencies=[Depends(require_feature("finance"))])

_REVENUE_STATUSES = ("confirmed", "processing", "shipped", "delivered")


def _require_manager(user: CurrentUser) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Owner or manager required")


def _emit(
    db: Session,
    business_id: Any,
    actor_id: Any,
    event_type: EventType,
    entity_type: str,
    entity_id: Any,
    description: str | None = None,
    data: dict | None = None,
) -> None:
    """Queue an event row in the same (not-yet-committed) transaction as the
    caller's pending business-row change - the caller commits once, after
    this call, so both persist atomically or neither does."""
    EventService(db).create_event(
        business_id=UUID(str(business_id)),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=UUID(str(entity_id)),
        actor_id=UUID(str(actor_id)) if actor_id else None,
        description=description,
        data=data,
        commit=False,
    )


def _period_bounds(period: str) -> tuple[date, date, str]:
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    if period == "this_month":
        start = date(y, m, 1)
        end = now.date()
        label = now.strftime("%B %Y")
    elif period == "last_month":
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
        import calendar
        last_day = calendar.monthrange(y, m)[1]
        start = date(y, m, 1)
        end = date(y, m, last_day)
        label = date(y, m, 1).strftime("%B %Y")
    elif period == "ytd":
        start = date(y, 1, 1)
        end = now.date()
        label = f"YTD {y}"
    else:  # this_year
        start = date(y, 1, 1)
        end = date(y, 12, 31)
        label = str(y)
    return start, end, label


def _expense_out(exp: Expense) -> ExpenseOut:
    out = ExpenseOut.model_validate(exp)
    out.category_name = exp.category.name if exp.category else None
    return out


# ── Summary ────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=FinanceSummary)
def get_summary(
    period: str = "this_month",
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    start, end, label = _period_bounds(period)
    bid = current_user.business_id

    revenue = (
        db.query(sa.func.coalesce(sa.func.sum(SalesOrder.total_amount), 0))
        .filter(
            SalesOrder.business_id == bid,
            SalesOrder.status.in_(_REVENUE_STATUSES),
            sa.func.date(SalesOrder.order_date) >= start,
            sa.func.date(SalesOrder.order_date) <= end,
        )
        .scalar()
    )

    expenses_total = (
        db.query(sa.func.coalesce(sa.func.sum(Expense.amount), 0))
        .filter(
            Expense.business_id == bid,
            Expense.date >= start,
            Expense.date <= end,
        )
        .scalar()
    )

    by_cat_rows = (
        db.query(
            sa.func.coalesce(ExpenseCategory.name, "Uncategorised"),
            sa.func.sum(Expense.amount),
        )
        .outerjoin(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .filter(Expense.business_id == bid, Expense.date >= start, Expense.date <= end)
        .group_by(ExpenseCategory.name)
        .all()
    )

    return FinanceSummary(
        period_label=label,
        revenue=Decimal(str(revenue)),
        expenses=Decimal(str(expenses_total)),
        net_profit=Decimal(str(revenue)) - Decimal(str(expenses_total)),
        expense_by_category=[CategoryTotal(name=r[0], amount=Decimal(str(r[1]))) for r in by_cat_rows],
    )


# ── Categories ─────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[ExpenseCategoryOut])
def list_categories(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return db.query(ExpenseCategory).filter(
        ExpenseCategory.business_id == current_user.business_id,
        ExpenseCategory.is_active.is_(True),
    ).order_by(ExpenseCategory.name).all()


@router.post("/categories", response_model=ExpenseCategoryOut, status_code=201)
def create_category(
    data: ExpenseCategoryCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    cat = ExpenseCategory(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/categories/{cat_id}", response_model=ExpenseCategoryOut)
def update_category(
    cat_id: UUID,
    data: ExpenseCategoryUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    cat = db.query(ExpenseCategory).filter(
        ExpenseCategory.id == cat_id,
        ExpenseCategory.business_id == current_user.business_id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


# ── Expenses ───────────────────────────────────────────────────────────────

@router.get("/expenses", response_model=ExpenseListResponse)
def list_expenses(
    skip: int = 0,
    limit: int = 20,
    category_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Expense).filter(Expense.business_id == current_user.business_id)
    if category_id:
        q = q.filter(Expense.category_id == category_id)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    total = q.count()
    rows = q.order_by(Expense.date.desc()).offset(skip).limit(limit).all()
    return ExpenseListResponse(
        items=[_expense_out(e) for e in rows],
        total=total, skip=skip, limit=limit,
    )


@router.get("/expenses/export")
def export_expenses(
    category_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Download all expenses as a CSV file."""
    q = db.query(Expense).filter(Expense.business_id == current_user.business_id)
    if category_id:
        q = q.filter(Expense.category_id == category_id)
    if from_date:
        q = q.filter(Expense.date >= from_date)
    if to_date:
        q = q.filter(Expense.date <= to_date)
    rows = q.order_by(Expense.date.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Description", "Vendor", "Category", "Amount (R)"])
    for exp in rows:
        writer.writerow([
            exp.date,
            exp.description or "",
            exp.vendor or "",
            exp.category.name if exp.category else "",
            exp.amount,
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    data: ExpenseCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    exp = Expense(
        id=uuid4(),
        business_id=current_user.business_id,
        paid_by=current_user.user_id,
        **data.model_dump(),
    )
    db.add(exp)
    db.flush()
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EXPENSE_CREATED, "expense", exp.id,
          description=f"Expense recorded: {exp.description or 'no description'} — R{float(exp.amount):,.2f}",
          data={"amount": float(exp.amount), "category_id": str(exp.category_id) if exp.category_id else None,
                "date": str(exp.date)})
    db.commit()
    db.refresh(exp)
    return _expense_out(exp)


@router.patch("/expenses/{exp_id}", response_model=ExpenseOut)
def update_expense(
    exp_id: UUID,
    data: ExpenseUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    exp = db.query(Expense).filter(
        Expense.id == exp_id, Expense.business_id == current_user.business_id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    updated_fields = list(data.model_dump(exclude_none=True).keys())
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(exp, k, v)
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EXPENSE_UPDATED, "expense", exp.id,
          description=f"Expense updated: {exp.description or 'no description'}",
          data={"updated_fields": updated_fields, "amount": float(exp.amount)})
    db.commit()
    db.refresh(exp)
    return _expense_out(exp)


@router.delete("/expenses/{exp_id}", status_code=204)
def delete_expense(
    exp_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    exp = db.query(Expense).filter(
        Expense.id == exp_id, Expense.business_id == current_user.business_id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    exp_id = exp.id
    exp_desc = exp.description or "no description"
    exp_amount = float(exp.amount)
    exp_date = str(exp.date)
    db.delete(exp)
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EXPENSE_DELETED, "expense", exp_id,
          description=f"Expense deleted: {exp_desc} — R{exp_amount:,.2f}",
          data={"amount": exp_amount, "date": exp_date})
    db.commit()
