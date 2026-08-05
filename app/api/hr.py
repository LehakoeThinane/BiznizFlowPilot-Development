"""HR & Payroll API — departments, employees, leave, payroll."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Annotated
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.entitlements import require_feature
from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES
from app.dependencies import get_current_user
from app.models.hr import Department, Employee, LeaveRequest, LeaveType, PayrollPeriod, Payslip
from app.models.payroll import DeductionType, EmployeeDeduction, Timesheet
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.schemas.auth import CurrentUser
from app.schemas.hr import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeOut,
    EmployeeUpdate,
    LeaveListResponse,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveStatusUpdate,
    LeaveTypeCreate,
    LeaveTypeOut,
    OrgChartNode,
    PayrollGenerateRequest,
    PayrollPeriodOut,
    PayslipAdjust,
    PayslipOut,
)
from app.services.event import EventService
from app.utils.notify import notify_business, notify_organization_role, notify_user

router = APIRouter(prefix="/api/v1/hr", tags=["hr"], dependencies=[Depends(require_feature("hr"))])


def _require_manager(user: CurrentUser) -> None:
    if user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Owner or manager required")


def _validate_employee_email_domain(db: Session, user: CurrentUser, email: str | None) -> None:
    """Reject employee emails outside the organization's authorized domains.

    No-op if the organization has no domains configured (opt-in restriction,
    same rule used for user invitations)."""
    if not email:
        return
    org_repo = OrganizationRepository(db)
    if not org_repo.domain_is_authorized(UUID(str(user.organization_id)), email):
        raise HTTPException(
            status_code=400,
            detail="This email's domain is not authorized for your organization",
        )


def _validate_employee_user_link(
    db: Session, business_id: Any, user_id: UUID, employee_id: UUID | None
) -> None:
    """A linked user_id must belong to this business and not already be linked
    to a different active employee."""
    user = db.query(User).filter(User.id == user_id, User.business_id == business_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found in this business")
    q = db.query(Employee).filter(Employee.user_id == user_id, Employee.is_active.is_(True))
    if employee_id:
        q = q.filter(Employee.id != employee_id)
    if q.first():
        raise HTTPException(status_code=400, detail="This user is already linked to another employee")


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


def _employee_out(emp: Employee) -> EmployeeOut:
    out = EmployeeOut.model_validate(emp)
    out.full_name = f"{emp.first_name} {emp.last_name}"
    out.department_name = emp.department.name if emp.department else None
    out.manager_name = f"{emp.manager.first_name} {emp.manager.last_name}" if emp.manager else None
    return out


def _assert_no_manager_cycle(db: Session, employee_id: UUID, manager_id: UUID) -> None:
    """Walk the proposed manager's chain; reject if it revisits employee_id."""
    if manager_id == employee_id:
        raise HTTPException(status_code=400, detail="An employee cannot be their own manager")
    current_id = manager_id
    for _ in range(50):
        mgr = db.query(Employee.manager_id).filter(Employee.id == current_id).first()
        if not mgr or not mgr[0]:
            return
        if mgr[0] == employee_id:
            raise HTTPException(status_code=400, detail="Invalid manager: would create a reporting cycle")
        current_id = mgr[0]
    raise HTTPException(status_code=400, detail="Invalid manager: reporting chain too deep")


# ── Departments ─────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    rows = db.query(Department).filter(
        Department.business_id == current_user.business_id,
        Department.is_active.is_(True),
    ).order_by(Department.name).all()

    # Single query for all employee counts — avoids N+1
    count_rows = (
        db.query(Employee.department_id, sa.func.count(Employee.id).label("cnt"))
        .filter(Employee.is_active.is_(True))
        .group_by(Employee.department_id)
        .all()
    )
    count_map = {row.department_id: row.cnt for row in count_rows}

    result = []
    for dept in rows:
        out = DepartmentOut.model_validate(dept)
        out.employee_count = count_map.get(dept.id, 0)
        result.append(out)
    return result


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(
    data: DepartmentCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    dept = Department(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    out = DepartmentOut.model_validate(dept)
    out.employee_count = 0
    return out


@router.patch("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: UUID,
    data: DepartmentUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.business_id == current_user.business_id,
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    out = DepartmentOut.model_validate(dept)
    out.employee_count = (
        db.query(sa.func.count(Employee.id))
        .filter(Employee.department_id == dept.id, Employee.is_active.is_(True))
        .scalar() or 0
    )
    return out


# ── Employees ───────────────────────────────────────────────────────────────

@router.get("/employees", response_model=EmployeeListResponse)
def list_employees(
    skip: int = 0,
    limit: int = 20,
    department_id: UUID | None = None,
    is_active: bool | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Employee).filter(Employee.business_id == current_user.business_id)
    if department_id:
        q = q.filter(Employee.department_id == department_id)
    if is_active is not None:
        q = q.filter(Employee.is_active.is_(is_active))
    total = q.count()
    rows = q.order_by(Employee.last_name, Employee.first_name).offset(skip).limit(limit).all()
    return EmployeeListResponse(
        items=[_employee_out(e) for e in rows],
        total=total, skip=skip, limit=limit,
    )


@router.get("/employees/org-chart", response_model=list[OrgChartNode])
def get_org_chart(
    include_inactive: bool = False,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Employee).filter(Employee.business_id == current_user.business_id)
    if not include_inactive:
        q = q.filter(Employee.is_active.is_(True))
    rows = q.all()
    return [
        OrgChartNode(
            id=e.id,
            full_name=f"{e.first_name} {e.last_name}",
            position=e.position,
            department_name=e.department.name if e.department else None,
            manager_id=e.manager_id,
            is_active=e.is_active,
            email=e.email,
        )
        for e in rows
    ]


@router.get("/employees/{emp_id}", response_model=EmployeeOut)
def get_employee(
    emp_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    emp = db.query(Employee).filter(
        Employee.id == emp_id, Employee.business_id == current_user.business_id
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _employee_out(emp)


@router.post("/employees", response_model=EmployeeOut, status_code=201)
def create_employee(
    data: EmployeeCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    _validate_employee_email_domain(db, current_user, data.email)
    if data.user_id:
        _validate_employee_user_link(db, current_user.business_id, data.user_id, None)
    new_id = uuid4()
    if data.manager_id:
        _assert_no_manager_cycle(db, new_id, data.manager_id)
    emp = Employee(id=new_id, business_id=current_user.business_id, **data.model_dump())
    db.add(emp)
    db.flush()
    notify_business(
        db, current_user.business_id, "system",
        "New employee added",
        f"{emp.first_name} {emp.last_name} has been added"
        + (f" as {emp.position}" if emp.position else "") + ".",
        action_url="/employees",
        related_type="employee", related_id=emp.id,
    )
    if not emp.user_id and current_user.organization_id:
        notify_organization_role(
            db, current_user.organization_id, "it_admin", "onboarding",
            "New employee needs a login",
            f"{emp.first_name} {emp.last_name} was added to HR but has no user account yet. "
            "Invite them if they need dashboard access.",
            action_url="/organization/invites",
            related_type="employee", related_id=emp.id,
        )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EMPLOYEE_CREATED, "employee", emp.id,
          description=f"Employee created: {emp.first_name} {emp.last_name}",
          data={"position": emp.position, "department_id": str(emp.department_id) if emp.department_id else None})
    db.commit()
    db.refresh(emp)
    return _employee_out(emp)


@router.patch("/employees/{emp_id}", response_model=EmployeeOut)
def update_employee(
    emp_id: UUID,
    data: EmployeeUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    _validate_employee_email_domain(db, current_user, data.email)
    emp = db.query(Employee).filter(
        Employee.id == emp_id, Employee.business_id == current_user.business_id
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if data.user_id:
        _validate_employee_user_link(db, current_user.business_id, data.user_id, emp.id)
    if data.manager_id:
        _assert_no_manager_cycle(db, emp.id, data.manager_id)
    updated_fields = list(data.model_dump(exclude_none=True).keys())
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(emp, k, v)
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EMPLOYEE_UPDATED, "employee", emp.id,
          description=f"Employee updated: {emp.first_name} {emp.last_name}",
          data={"updated_fields": updated_fields})
    db.commit()
    db.refresh(emp)
    return _employee_out(emp)


@router.delete("/employees/{emp_id}", status_code=204)
def delete_employee(
    emp_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    emp = db.query(Employee).filter(
        Employee.id == emp_id, Employee.business_id == current_user.business_id
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_name = f"{emp.first_name} {emp.last_name}"
    emp_id = emp.id
    emp.is_active = False
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.EMPLOYEE_DEACTIVATED, "employee", emp_id,
          description=f"Employee deactivated: {emp_name}")
    db.commit()


# ── Leave Types ─────────────────────────────────────────────────────────────

@router.get("/leave-types", response_model=list[LeaveTypeOut])
def list_leave_types(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    return db.query(LeaveType).filter(
        LeaveType.business_id == current_user.business_id,
        LeaveType.is_active.is_(True),
    ).order_by(LeaveType.name).all()


@router.post("/leave-types", response_model=LeaveTypeOut, status_code=201)
def create_leave_type(
    data: LeaveTypeCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    lt = LeaveType(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


# ── Leave Requests ──────────────────────────────────────────────────────────

def _leave_out(req: LeaveRequest) -> LeaveRequestOut:
    out = LeaveRequestOut.model_validate(req)
    if req.employee:
        out.employee_name = f"{req.employee.first_name} {req.employee.last_name}"
    out.leave_type_name = req.leave_type.name if req.leave_type else None
    return out


@router.get("/leave-requests", response_model=LeaveListResponse)
def list_leave_requests(
    skip: int = 0,
    limit: int = 20,
    employee_id: UUID | None = None,
    status: str | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = (
        db.query(LeaveRequest)
        .join(Employee, LeaveRequest.employee_id == Employee.id)
        .filter(Employee.business_id == current_user.business_id)
    )
    if employee_id:
        q = q.filter(LeaveRequest.employee_id == employee_id)
    if status:
        q = q.filter(LeaveRequest.status == status)
    total = q.count()
    rows = q.order_by(LeaveRequest.created_at.desc()).offset(skip).limit(limit).all()
    return LeaveListResponse(
        items=[_leave_out(r) for r in rows],
        total=total, skip=skip, limit=limit,
    )


@router.post("/leave-requests", response_model=LeaveRequestOut, status_code=201)
def create_leave_request(
    data: LeaveRequestCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    emp = db.query(Employee).filter(
        Employee.id == data.employee_id,
        Employee.business_id == current_user.business_id,
    ).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    req = LeaveRequest(id=uuid4(), business_id=current_user.business_id, **data.model_dump())
    db.add(req)
    db.flush()
    notify_business(
        db, current_user.business_id, "leave",
        "Leave request submitted",
        f"{emp.first_name} {emp.last_name} requested {data.days_requested} day(s) leave"
        f" from {data.start_date} to {data.end_date}.",
        action_url="/leave", related_type="leave_request", related_id=req.id,
    )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.LEAVE_REQUESTED, "leave_request", req.id,
          description=f"Leave requested by {emp.first_name} {emp.last_name}: {data.start_date} – {data.end_date}",
          data={"employee_id": str(data.employee_id), "days": int(data.days_requested),
                "start_date": str(data.start_date), "end_date": str(data.end_date)})
    db.commit()
    db.refresh(req)
    return _leave_out(req)


@router.patch("/leave-requests/{req_id}/status", response_model=LeaveRequestOut)
def update_leave_status(
    req_id: UUID,
    data: LeaveStatusUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    req = (
        db.query(LeaveRequest)
        .join(Employee, LeaveRequest.employee_id == Employee.id)
        .filter(LeaveRequest.id == req_id, Employee.business_id == current_user.business_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    emp_name = f"{req.employee.first_name} {req.employee.last_name}" if req.employee else "Employee"
    req.status = data.status
    if data.status in ("approved", "rejected", "completed"):
        req.approved_by = current_user.user_id
        req.approved_at = datetime.now(timezone.utc)
    if data.notes:
        req.notes = data.notes
    notify_business(
        db, current_user.business_id, "leave",
        f"Leave request {data.status}",
        f"{emp_name}'s leave request ({req.start_date} – {req.end_date}) was {data.status}.",
        action_url="/leave", related_type="leave_request", related_id=req.id,
    )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.LEAVE_STATUS_CHANGED, "leave_request", req.id,
          description=f"Leave {data.status} for {emp_name}: {req.start_date} – {req.end_date}",
          data={"status": data.status, "notes": data.notes})
    db.commit()
    db.refresh(req)
    return _leave_out(req)


# ── Payroll ─────────────────────────────────────────────────────────────────

_PAYE_BRACKETS = [
    (237_100, Decimal("0.18"), Decimal("0")),
    (370_500, Decimal("0.26"), Decimal("42_678")),
    (512_800, Decimal("0.31"), Decimal("77_362")),
    (673_000, Decimal("0.36"), Decimal("121_475")),
    (857_900, Decimal("0.39"), Decimal("179_147")),
    (1_817_000, Decimal("0.41"), Decimal("251_258")),
    (float("inf"), Decimal("0.45"), Decimal("644_489")),
]
_UIF_RATE = Decimal("0.01")
_UIF_CAP = Decimal("177.12")
_MONTHS = Decimal("12")


def _calc_paye(annual_gross: Decimal) -> Decimal:
    ag = float(annual_gross)
    prev_threshold = 0.0
    for threshold, rate, base in _PAYE_BRACKETS:
        if ag <= threshold:
            annual_tax = base + Decimal(str(ag - prev_threshold)) * rate
            rebate = Decimal("17_235")
            annual_tax = max(annual_tax - rebate, Decimal("0"))
            return (annual_tax / _MONTHS).quantize(Decimal("0.01"))
        prev_threshold = float(threshold)
    return Decimal("0")


def _calc_uif(monthly_gross: Decimal) -> Decimal:
    return min(monthly_gross * _UIF_RATE, _UIF_CAP).quantize(Decimal("0.01"))


def _calc_employee_deductions(db: Session, employee_id: UUID, gross: Decimal) -> Decimal:
    """Sum an employee's active configured deductions for one payslip.

    Fringe-benefit tax treatment (e.g. medical aid tax credits) isn't
    modeled yet - this only sums flat/percent-of-gross deductions."""
    rows = (
        db.query(EmployeeDeduction, DeductionType)
        .join(DeductionType, EmployeeDeduction.deduction_type_id == DeductionType.id)
        .filter(EmployeeDeduction.employee_id == employee_id, EmployeeDeduction.is_active.is_(True))
        .all()
    )
    total = Decimal("0")
    for assignment, dtype in rows:
        amount = assignment.amount_override if assignment.amount_override is not None else dtype.default_amount
        if amount is None:
            continue
        if dtype.calculation == "percent_of_gross":
            total += (gross * amount / Decimal("100")).quantize(Decimal("0.01"))
        else:
            total += amount
    return total


@router.post("/payroll/generate", response_model=PayrollPeriodOut, status_code=201)
def generate_payroll(
    data: PayrollGenerateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)

    existing = db.query(PayrollPeriod).filter(
        PayrollPeriod.business_id == current_user.business_id,
        PayrollPeriod.period_year == data.period_year,
        PayrollPeriod.period_month == data.period_month,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Payroll already generated for this period")

    employees = db.query(Employee).filter(
        Employee.business_id == current_user.business_id,
        Employee.is_active.is_(True),
    ).all()

    period_start = date(data.period_year, data.period_month, 1)
    period_end = date(
        data.period_year, data.period_month,
        calendar.monthrange(data.period_year, data.period_month)[1],
    )

    period = PayrollPeriod(
        id=uuid4(),
        business_id=current_user.business_id,
        period_year=data.period_year,
        period_month=data.period_month,
        notes=data.notes,
        status="draft",
        total_gross=Decimal("0"),
        total_deductions=Decimal("0"),
        total_net=Decimal("0"),
    )
    db.add(period)
    db.flush()

    total_gross = Decimal("0")
    total_deductions = Decimal("0")
    total_net = Decimal("0")

    for emp in employees:
        if emp.salary_type == "hourly":
            hours = db.query(sa.func.coalesce(sa.func.sum(Timesheet.hours_worked), 0)).filter(
                Timesheet.employee_id == emp.id,
                Timesheet.work_date >= period_start,
                Timesheet.work_date <= period_end,
            ).scalar()
            if not hours:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No timesheet entries logged for {emp.first_name} {emp.last_name} "
                        f"in {calendar.month_name[data.period_month]} {data.period_year} — "
                        "log hours before generating payroll for an hourly employee."
                    ),
                )
            gross = (emp.gross_salary * Decimal(str(hours))).quantize(Decimal("0.01"))
            annual_gross = gross * _MONTHS
        elif emp.salary_type == "monthly":
            gross = emp.gross_salary
            annual_gross = emp.gross_salary * _MONTHS
        else:  # annual
            gross = emp.gross_salary / _MONTHS
            annual_gross = emp.gross_salary

        paye = _calc_paye(annual_gross)
        uif = _calc_uif(gross)
        other_deductions = _calc_employee_deductions(db, emp.id, gross)
        deductions = paye + uif + other_deductions
        net = gross - deductions

        slip = Payslip(
            id=uuid4(),
            business_id=current_user.business_id,
            payroll_period_id=period.id,
            employee_id=emp.id,
            basic_pay=gross,
            overtime_pay=Decimal("0"),
            bonus=Decimal("0"),
            gross_pay=gross,
            tax_deduction=paye,
            uif_deduction=uif,
            other_deductions=other_deductions,
            total_deductions=deductions,
            net_pay=net,
            status="draft",
        )
        db.add(slip)
        total_gross += gross
        total_deductions += deductions
        total_net += net

    period.total_gross = total_gross
    period.total_deductions = total_deductions
    period.total_net = total_net

    # Notification + audit event are queued in the same transaction as the
    # period/payslip rows above - committed together below, atomically.
    month_name = calendar.month_name[data.period_month]
    notify_business(
        db, current_user.business_id, "payroll",
        "Payroll generated",
        f"Payroll for {month_name} {data.period_year} has been generated"
        f" for {len(employees)} employee(s). Total net: R{total_net:,.2f}.",
        action_url="/payroll", related_type="payroll_period", related_id=period.id,
    )
    _emit(db, current_user.business_id, current_user.user_id,
          EventType.PAYROLL_GENERATED, "payroll_period", period.id,
          description=f"Payroll generated for {month_name} {data.period_year}: {len(employees)} employees, net R{total_net:,.2f}",
          data={"period_year": data.period_year, "period_month": data.period_month,
                "employee_count": len(employees), "total_net": float(total_net)})

    db.commit()
    db.refresh(period)

    slips = db.query(Payslip).filter(Payslip.payroll_period_id == period.id).all()
    out = PayrollPeriodOut.model_validate(period)
    payslip_outs = []
    for slip in slips:
        s = PayslipOut.model_validate(slip)
        emp = next((e for e in employees if e.id == slip.employee_id), None)
        s.employee_name = f"{emp.first_name} {emp.last_name}" if emp else ""
        payslip_outs.append(s)
    out.payslips = payslip_outs
    return out


@router.get("/payroll", response_model=list[PayrollPeriodOut])
def list_payroll_periods(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    periods = db.query(PayrollPeriod).filter(
        PayrollPeriod.business_id == current_user.business_id
    ).order_by(PayrollPeriod.period_year.desc(), PayrollPeriod.period_month.desc()).all()
    result = []
    for period in periods:
        out = PayrollPeriodOut.model_validate(period)
        out.payslips = []
        result.append(out)
    return result


@router.get("/payroll/{period_id}", response_model=PayrollPeriodOut)
def get_payroll_period(
    period_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.id == period_id,
        PayrollPeriod.business_id == current_user.business_id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    slips = db.query(Payslip).filter(Payslip.payroll_period_id == period_id).all()

    # Preload all referenced employees in one query — avoids N+1
    emp_ids = {slip.employee_id for slip in slips}
    emp_map = {
        emp.id: emp
        for emp in db.query(Employee).filter(Employee.id.in_(emp_ids)).all()
    } if emp_ids else {}

    out = PayrollPeriodOut.model_validate(period)
    payslip_outs = []
    for slip in slips:
        s = PayslipOut.model_validate(slip)
        emp = emp_map.get(slip.employee_id)
        s.employee_name = f"{emp.first_name} {emp.last_name}" if emp else ""
        payslip_outs.append(s)
    out.payslips = payslip_outs
    return out


@router.patch("/payroll/{period_id}/approve", response_model=PayrollPeriodOut)
def approve_payroll(
    period_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _require_manager(current_user)
    period = db.query(PayrollPeriod).filter(
        PayrollPeriod.id == period_id,
        PayrollPeriod.business_id == current_user.business_id,
    ).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft payroll can be approved")
    period.status = "completed"
    period.processed_at = datetime.now(timezone.utc)
    db.query(Payslip).filter(Payslip.payroll_period_id == period_id).update({"status": "finalized"})

    slips = db.query(Payslip).filter(Payslip.payroll_period_id == period_id).all()
    emp_map = {
        e.id: e for e in db.query(Employee).filter(
            Employee.id.in_({s.employee_id for s in slips})
        ).all()
    } if slips else {}
    month_name = calendar.month_name[period.period_month]
    for slip in slips:
        emp = emp_map.get(slip.employee_id)
        if emp and emp.user_id:
            notify_user(
                db, current_user.business_id, emp.user_id, "payroll",
                "Payslip ready",
                f"Your payslip for {month_name} {period.period_year} is ready. Net pay: R{slip.net_pay:,.2f}.",
                action_url="/payroll", related_type="payslip", related_id=slip.id,
            )
    notify_business(
        db, current_user.business_id, "payroll",
        "Payroll approved",
        f"Payroll for {month_name} {period.period_year} has been approved and finalized.",
        action_url="/payroll", related_type="payroll_period", related_id=period.id,
    )

    _emit(db, current_user.business_id, current_user.user_id,
          EventType.PAYROLL_APPROVED, "payroll_period", period.id,
          description=f"Payroll approved: {period.period_month}/{period.period_year}",
          data={"period_year": period.period_year, "period_month": period.period_month,
                "total_net": float(period.total_net)})
    db.commit()
    db.refresh(period)
    return get_payroll_period(period_id, current_user, db)


@router.patch("/payroll/payslips/{payslip_id}", response_model=PayslipOut)
def adjust_payslip(
    payslip_id: UUID,
    data: PayslipAdjust,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Adjust a draft payslip's bonus/overtime/other-deductions and recompute
    its and its period's totals. Only permitted while the period is a draft —
    once approved, payslips are finalized and immutable."""
    _require_manager(current_user)
    slip = db.query(Payslip).filter(
        Payslip.id == payslip_id, Payslip.business_id == current_user.business_id
    ).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == slip.payroll_period_id).first()
    if not period or period.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Payslips can only be adjusted while the payroll period is a draft",
        )

    updates = data.model_dump(exclude_none=True)
    for k, v in updates.items():
        setattr(slip, k, v)

    slip.gross_pay = slip.basic_pay + slip.overtime_pay + slip.bonus
    slip.total_deductions = slip.tax_deduction + slip.uif_deduction + slip.other_deductions
    slip.net_pay = slip.gross_pay - slip.total_deductions

    # Recompute the parent period's totals from all its payslips (this one just changed).
    all_slips = db.query(Payslip).filter(Payslip.payroll_period_id == period.id).all()
    period.total_gross = sum((s.gross_pay for s in all_slips), Decimal("0"))
    period.total_deductions = sum((s.total_deductions for s in all_slips), Decimal("0"))
    period.total_net = sum((s.net_pay for s in all_slips), Decimal("0"))

    _emit(db, current_user.business_id, current_user.user_id,
          EventType.PAYSLIP_ADJUSTED, "payslip", slip.id,
          description=f"Payslip adjusted for {period.period_month}/{period.period_year}",
          data={"updated_fields": list(updates.keys())})
    db.commit()
    db.refresh(slip)

    emp = db.query(Employee).filter(Employee.id == slip.employee_id).first()
    out = PayslipOut.model_validate(slip)
    out.employee_name = f"{emp.first_name} {emp.last_name}" if emp else ""
    return out


@router.get("/payroll/payslips/{payslip_id}/pdf", response_class=HTMLResponse)
def payslip_pdf(
    payslip_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Return a print-ready HTML page for the payslip (open in browser → Print → Save as PDF)."""
    slip = db.query(Payslip).filter(
        Payslip.id == payslip_id, Payslip.business_id == current_user.business_id
    ).first()
    if not slip:
        raise HTTPException(status_code=404, detail="Payslip not found")
    emp = db.query(Employee).filter(Employee.id == slip.employee_id).first()
    period = db.query(PayrollPeriod).filter(PayrollPeriod.id == slip.payroll_period_id).first()
    month_name = calendar.month_name[period.period_month] if period else ""
    emp_name = f"{emp.first_name} {emp.last_name}" if emp else "—"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Payslip - {emp_name} - {month_name} {period.period_year if period else ""}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Arial, sans-serif; font-size: 13px; color: #1a1a1a; padding: 40px; }}
    h1 {{ font-size: 28px; font-weight: 800; color: #1e3a8a; }}
    .meta {{ display: flex; justify-content: space-between; margin: 24px 0; }}
    .block {{ line-height: 1.7; }}
    .block strong {{ display: block; font-size: 11px; text-transform: uppercase;
                     letter-spacing: .05em; color: #666; margin-bottom: 2px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
    th {{ background: #f1f5f9; text-align: left; padding: 8px 10px;
          font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
    .totals {{ margin-top: 16px; text-align: right; }}
    .totals table {{ width: auto; margin-left: auto; }}
    .totals td {{ padding: 4px 10px; border: none; }}
    .totals .total-row td {{ font-size: 16px; font-weight: 700; color: #1e3a8a; }}
    .status {{ display: inline-block; padding: 4px 12px; border-radius: 20px;
               font-size: 11px; font-weight: 700; text-transform: uppercase;
               background: #dbeafe; color: #1e40af; margin-bottom: 8px; }}
    @media print {{ body {{ padding: 0; }} }}
  </style>
</head>
<body>
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <h1>PAYSLIP</h1>
      <div class="status">{slip.status.upper()}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:20px;font-weight:700">{month_name} {period.period_year if period else ""}</div>
    </div>
  </div>

  <div class="meta">
    <div class="block">
      <strong>Employee</strong>
      {emp_name}<br/>
      {emp.position or "" if emp else ""}
    </div>
  </div>

  <table>
    <thead>
      <tr><th>Description</th><th style="text-align:right">Amount</th></tr>
    </thead>
    <tbody>
      <tr><td>Basic pay</td><td style="text-align:right">R {slip.basic_pay:,.2f}</td></tr>
      <tr><td>Overtime</td><td style="text-align:right">R {slip.overtime_pay:,.2f}</td></tr>
      <tr><td>Bonus</td><td style="text-align:right">R {slip.bonus:,.2f}</td></tr>
      <tr><td>PAYE</td><td style="text-align:right">- R {slip.tax_deduction:,.2f}</td></tr>
      <tr><td>UIF</td><td style="text-align:right">- R {slip.uif_deduction:,.2f}</td></tr>
      <tr><td>Other deductions</td><td style="text-align:right">- R {slip.other_deductions:,.2f}</td></tr>
    </tbody>
  </table>

  <div class="totals">
    <table>
      <tr><td>Gross pay</td><td>R {slip.gross_pay:,.2f}</td></tr>
      <tr><td>Total deductions</td><td>- R {slip.total_deductions:,.2f}</td></tr>
      <tr class="total-row"><td>Net pay</td><td>R {slip.net_pay:,.2f}</td></tr>
    </table>
  </div>

  <script>window.onload = () => window.print();</script>
</body>
</html>"""
    return HTMLResponse(content=html)
