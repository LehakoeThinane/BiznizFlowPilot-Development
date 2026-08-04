"""Payroll schemas — deduction/benefit types, employee assignments, timesheets."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Calculation = Literal["fixed_amount", "percent_of_gross"]


# ── Deduction types ──────────────────────────────────────────────────────────

class DeductionTypeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    calculation: Calculation = "fixed_amount"
    default_amount: Decimal | None = None


class DeductionTypeUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    calculation: Calculation | None = None
    default_amount: Decimal | None = None
    is_active: bool | None = None


class DeductionTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    calculation: str
    default_amount: Decimal | None
    is_active: bool
    created_at: datetime


# ── Benefit types ────────────────────────────────────────────────────────────

class BenefitTypeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    calculation: Calculation = "fixed_amount"
    default_amount: Decimal | None = None


class BenefitTypeUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    calculation: Calculation | None = None
    default_amount: Decimal | None = None
    is_active: bool | None = None


class BenefitTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    calculation: str
    default_amount: Decimal | None
    is_active: bool
    created_at: datetime


# ── Employee assignments ─────────────────────────────────────────────────────

class EmployeeDeductionCreate(BaseModel):
    employee_id: UUID
    deduction_type_id: UUID
    amount_override: Decimal | None = None


class EmployeeDeductionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    deduction_type_id: UUID
    deduction_type_name: str = ""
    amount_override: Decimal | None
    is_active: bool


class EmployeeBenefitCreate(BaseModel):
    employee_id: UUID
    benefit_type_id: UUID
    amount_override: Decimal | None = None


class EmployeeBenefitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    benefit_type_id: UUID
    benefit_type_name: str = ""
    amount_override: Decimal | None
    is_active: bool


# ── Timesheets ───────────────────────────────────────────────────────────────

class TimesheetCreate(BaseModel):
    employee_id: UUID
    work_date: date
    hours_worked: Decimal
    notes: str | None = Field(None, max_length=1000)


class TimesheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    work_date: date
    hours_worked: Decimal
    notes: str | None
    created_at: datetime


class TimesheetListResponse(BaseModel):
    items: list[TimesheetOut]
    total: int
    skip: int
    limit: int
