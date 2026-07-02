"""HR models — departments, employees, leave, payroll."""

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

_employment_type = ENUM("full_time", "part_time", "contractor", "intern", name="employment_type", create_type=False)
_salary_type     = ENUM("monthly", "hourly", "annual",                    name="salary_type",     create_type=False)
_leave_status    = ENUM("pending", "approved", "rejected", "cancelled",   name="leave_status",    create_type=False)
_payroll_status  = ENUM("draft", "processing", "completed", "cancelled",  name="payroll_status",  create_type=False)
_payslip_status  = ENUM("draft", "finalized",                             name="payslip_status",  create_type=False)


class Department(BaseModel):
    __tablename__ = "departments"

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    employees = relationship("Employee", back_populates="department")


class Employee(BaseModel):
    __tablename__ = "employees"
    __table_args__ = (
        Index("ix_employees_biz_active", "business_id", "is_active"),
        Index("ix_employees_department", "department_id"),
    )

    business_id     = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id   = Column(Uuid, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    user_id         = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    first_name      = Column(String(100), nullable=False)
    last_name       = Column(String(100), nullable=False)
    email           = Column(String(255), nullable=True)
    phone           = Column(String(50),  nullable=True)
    position        = Column(String(150), nullable=True)
    national_id     = Column(String(50),  nullable=True)
    tax_number      = Column(String(50),  nullable=True)
    bank_account    = Column(String(100), nullable=True)

    employment_type = Column(_employment_type, nullable=False, server_default="full_time")
    salary_type     = Column(_salary_type,     nullable=False, server_default="monthly")
    gross_salary    = Column(Numeric(12, 2),   nullable=False, server_default="0")

    start_date      = Column(Date, nullable=True)
    end_date        = Column(Date, nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True, server_default="true")
    notes           = Column(Text, nullable=True)

    department  = relationship("Department", back_populates="employees")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    payslips    = relationship("Payslip", back_populates="employee")


class LeaveType(BaseModel):
    __tablename__ = "leave_types"

    business_id         = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name                = Column(String(100), nullable=False)
    default_days        = Column(Numeric(5, 1), nullable=False, server_default="0")
    is_paid             = Column(Boolean, nullable=False, default=True, server_default="true")
    is_active           = Column(Boolean, nullable=False, default=True, server_default="true")

    leave_requests = relationship("LeaveRequest", back_populates="leave_type")


class LeaveRequest(BaseModel):
    __tablename__ = "leave_requests"
    __table_args__ = (Index("ix_leave_requests_employee", "employee_id", "status"),)

    business_id     = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id     = Column(Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type_id   = Column(Uuid, ForeignKey("leave_types.id", ondelete="SET NULL"), nullable=True)
    start_date      = Column(Date, nullable=False)
    end_date        = Column(Date, nullable=False)
    days_requested  = Column(Numeric(5, 1), nullable=False)
    status          = Column(_leave_status, nullable=False, server_default="pending")
    reason          = Column(Text, nullable=True)
    approved_by     = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    notes           = Column(Text, nullable=True)

    employee    = relationship("Employee", back_populates="leave_requests")
    leave_type  = relationship("LeaveType", back_populates="leave_requests")


class PayrollPeriod(BaseModel):
    __tablename__ = "payroll_periods"
    __table_args__ = (Index("ix_payroll_periods_biz", "business_id", "period_year", "period_month"),)

    business_id       = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    period_year       = Column(Integer, nullable=False)
    period_month      = Column(Integer, nullable=False)
    status            = Column(_payroll_status, nullable=False, server_default="draft")
    total_gross       = Column(Numeric(14, 2), nullable=False, server_default="0")
    total_deductions  = Column(Numeric(14, 2), nullable=False, server_default="0")
    total_net         = Column(Numeric(14, 2), nullable=False, server_default="0")
    processed_by      = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at      = Column(DateTime(timezone=True), nullable=True)
    notes             = Column(Text, nullable=True)

    payslips = relationship("Payslip", back_populates="period", cascade="all, delete-orphan")


class Payslip(BaseModel):
    __tablename__ = "payslips"
    __table_args__ = (Index("ix_payslips_period_employee", "payroll_period_id", "employee_id"),)

    business_id       = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    payroll_period_id = Column(Uuid, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False)
    employee_id       = Column(Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)

    basic_pay         = Column(Numeric(12, 2), nullable=False)
    overtime_pay      = Column(Numeric(12, 2), nullable=False, server_default="0")
    bonus             = Column(Numeric(12, 2), nullable=False, server_default="0")
    gross_pay         = Column(Numeric(12, 2), nullable=False)
    tax_deduction     = Column(Numeric(12, 2), nullable=False, server_default="0")
    uif_deduction     = Column(Numeric(12, 2), nullable=False, server_default="0")
    other_deductions  = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_deductions  = Column(Numeric(12, 2), nullable=False, server_default="0")
    net_pay           = Column(Numeric(12, 2), nullable=False)
    status            = Column(_payslip_status, nullable=False, server_default="draft")
    notes             = Column(Text, nullable=True)

    period   = relationship("PayrollPeriod", back_populates="payslips")
    employee = relationship("Employee", back_populates="payslips")
