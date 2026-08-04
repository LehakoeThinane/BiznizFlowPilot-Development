"""Payroll configuration API — deduction/benefit types, employee assignments,
timesheets. Sits alongside app/api/hr.py (payroll generation/approval) as a
separate sibling router rather than growing that already-large file further."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.core.permissions import PRIVILEGED_ROLES
from app.dependencies import get_current_user
from app.models.hr import Employee
from app.models.payroll import BenefitType, DeductionType, EmployeeBenefit, EmployeeDeduction, Timesheet
from app.schemas.auth import CurrentUser
from app.schemas.payroll import (
    BenefitTypeCreate,
    BenefitTypeOut,
    BenefitTypeUpdate,
    DeductionTypeCreate,
    DeductionTypeOut,
    DeductionTypeUpdate,
    EmployeeBenefitCreate,
    EmployeeBenefitOut,
    EmployeeDeductionCreate,
    EmployeeDeductionOut,
    TimesheetCreate,
    TimesheetListResponse,
    TimesheetOut,
)

router = APIRouter(prefix="/api/v1/hr", tags=["payroll"], dependencies=[Depends(require_feature("hr"))])


def _require_manager(user: CurrentUser) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Owner or manager required")


def _get_employee(db: Session, business_id, employee_id: UUID) -> Employee:
    emp = db.query(Employee).filter(
        Employee.id == employee_id, Employee.business_id == business_id
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


# ── Deduction types ──────────────────────────────────────────────────────────

@router.get("/deduction-types", response_model=list[DeductionTypeOut])
def list_deduction_types(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return db.query(DeductionType).filter(
        DeductionType.business_id == current_user.business_id,
        DeductionType.is_active.is_(True),
    ).order_by(DeductionType.name).all()


@router.post("/deduction-types", response_model=DeductionTypeOut, status_code=201)
def create_deduction_type(
    data: DeductionTypeCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    dt = DeductionType(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt


@router.patch("/deduction-types/{dt_id}", response_model=DeductionTypeOut)
def update_deduction_type(
    dt_id: UUID,
    data: DeductionTypeUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    dt = db.query(DeductionType).filter(
        DeductionType.id == dt_id, DeductionType.business_id == current_user.business_id
    ).first()
    if not dt:
        raise HTTPException(status_code=404, detail="Deduction type not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(dt, k, v)
    db.commit()
    db.refresh(dt)
    return dt


# ── Benefit types ────────────────────────────────────────────────────────────

@router.get("/benefit-types", response_model=list[BenefitTypeOut])
def list_benefit_types(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return db.query(BenefitType).filter(
        BenefitType.business_id == current_user.business_id,
        BenefitType.is_active.is_(True),
    ).order_by(BenefitType.name).all()


@router.post("/benefit-types", response_model=BenefitTypeOut, status_code=201)
def create_benefit_type(
    data: BenefitTypeCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    bt = BenefitType(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(bt)
    db.commit()
    db.refresh(bt)
    return bt


@router.patch("/benefit-types/{bt_id}", response_model=BenefitTypeOut)
def update_benefit_type(
    bt_id: UUID,
    data: BenefitTypeUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    bt = db.query(BenefitType).filter(
        BenefitType.id == bt_id, BenefitType.business_id == current_user.business_id
    ).first()
    if not bt:
        raise HTTPException(status_code=404, detail="Benefit type not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(bt, k, v)
    db.commit()
    db.refresh(bt)
    return bt


# ── Employee deduction/benefit assignments ──────────────────────────────────

@router.get("/employee-deductions", response_model=list[EmployeeDeductionOut])
def list_employee_deductions(
    employee_id: UUID | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(EmployeeDeduction).filter(
        EmployeeDeduction.business_id == current_user.business_id,
        EmployeeDeduction.is_active.is_(True),
    )
    if employee_id:
        q = q.filter(EmployeeDeduction.employee_id == employee_id)
    rows = q.all()
    result = []
    for row in rows:
        out = EmployeeDeductionOut.model_validate(row)
        out.employee_name = f"{row.employee.first_name} {row.employee.last_name}" if row.employee else ""
        out.deduction_type_name = row.deduction_type.name if row.deduction_type else ""
        result.append(out)
    return result


@router.post("/employee-deductions", response_model=EmployeeDeductionOut, status_code=201)
def create_employee_deduction(
    data: EmployeeDeductionCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    emp = _get_employee(db, current_user.business_id, data.employee_id)
    dt = db.query(DeductionType).filter(
        DeductionType.id == data.deduction_type_id, DeductionType.business_id == current_user.business_id
    ).first()
    if not dt:
        raise HTTPException(status_code=404, detail="Deduction type not found")
    row = EmployeeDeduction(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = EmployeeDeductionOut.model_validate(row)
    out.employee_name = f"{emp.first_name} {emp.last_name}"
    out.deduction_type_name = dt.name
    return out


@router.delete("/employee-deductions/{row_id}", status_code=204)
def delete_employee_deduction(
    row_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    row = db.query(EmployeeDeduction).filter(
        EmployeeDeduction.id == row_id, EmployeeDeduction.business_id == current_user.business_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee deduction not found")
    db.delete(row)
    db.commit()


@router.get("/employee-benefits", response_model=list[EmployeeBenefitOut])
def list_employee_benefits(
    employee_id: UUID | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(EmployeeBenefit).filter(
        EmployeeBenefit.business_id == current_user.business_id,
        EmployeeBenefit.is_active.is_(True),
    )
    if employee_id:
        q = q.filter(EmployeeBenefit.employee_id == employee_id)
    rows = q.all()
    result = []
    for row in rows:
        out = EmployeeBenefitOut.model_validate(row)
        out.employee_name = f"{row.employee.first_name} {row.employee.last_name}" if row.employee else ""
        out.benefit_type_name = row.benefit_type.name if row.benefit_type else ""
        result.append(out)
    return result


@router.post("/employee-benefits", response_model=EmployeeBenefitOut, status_code=201)
def create_employee_benefit(
    data: EmployeeBenefitCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    emp = _get_employee(db, current_user.business_id, data.employee_id)
    bt = db.query(BenefitType).filter(
        BenefitType.id == data.benefit_type_id, BenefitType.business_id == current_user.business_id
    ).first()
    if not bt:
        raise HTTPException(status_code=404, detail="Benefit type not found")
    row = EmployeeBenefit(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = EmployeeBenefitOut.model_validate(row)
    out.employee_name = f"{emp.first_name} {emp.last_name}"
    out.benefit_type_name = bt.name
    return out


@router.delete("/employee-benefits/{row_id}", status_code=204)
def delete_employee_benefit(
    row_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    row = db.query(EmployeeBenefit).filter(
        EmployeeBenefit.id == row_id, EmployeeBenefit.business_id == current_user.business_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee benefit not found")
    db.delete(row)
    db.commit()


# ── Timesheets ───────────────────────────────────────────────────────────────

def _timesheet_out(ts: Timesheet) -> TimesheetOut:
    out = TimesheetOut.model_validate(ts)
    out.employee_name = f"{ts.employee.first_name} {ts.employee.last_name}" if ts.employee else ""
    return out


@router.get("/timesheets", response_model=TimesheetListResponse)
def list_timesheets(
    skip: int = 0,
    limit: int = 20,
    employee_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Timesheet).filter(Timesheet.business_id == current_user.business_id)
    if employee_id:
        q = q.filter(Timesheet.employee_id == employee_id)
    if date_from:
        q = q.filter(Timesheet.work_date >= date_from)
    if date_to:
        q = q.filter(Timesheet.work_date <= date_to)
    total = q.count()
    rows = q.order_by(Timesheet.work_date.desc()).offset(skip).limit(limit).all()
    return TimesheetListResponse(
        items=[_timesheet_out(r) for r in rows],
        total=total, skip=skip, limit=limit,
    )


@router.post("/timesheets", response_model=TimesheetOut, status_code=201)
def create_timesheet(
    data: TimesheetCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    # No manager gate — self-reported hours, same "submit now, get relied on
    # later" shape as leave requests (create_leave_request has no manager gate
    # either); a manager still controls what's paid out via payroll approval.
    _get_employee(db, current_user.business_id, data.employee_id)
    ts = Timesheet(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return _timesheet_out(ts)


@router.delete("/timesheets/{ts_id}", status_code=204)
def delete_timesheet(
    ts_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    ts = db.query(Timesheet).filter(
        Timesheet.id == ts_id, Timesheet.business_id == current_user.business_id
    ).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    db.delete(ts)
    db.commit()
