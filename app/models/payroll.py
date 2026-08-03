"""Payroll models — configurable deduction/benefit types and timesheets."""

from sqlalchemy import Boolean, Column, Date, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

_calculation = ENUM("fixed_amount", "percent_of_gross", name="pay_component_calculation", create_type=False)


class DeductionType(BaseModel):
    __tablename__ = "deduction_types"

    business_id     = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name            = Column(String(100), nullable=False)
    calculation     = Column(_calculation, nullable=False, server_default="fixed_amount")
    default_amount  = Column(Numeric(12, 2), nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True, server_default="true")

    employee_deductions = relationship("EmployeeDeduction", back_populates="deduction_type")


class BenefitType(BaseModel):
    __tablename__ = "benefit_types"

    business_id     = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name            = Column(String(100), nullable=False)
    calculation     = Column(_calculation, nullable=False, server_default="fixed_amount")
    default_amount  = Column(Numeric(12, 2), nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True, server_default="true")

    employee_benefits = relationship("EmployeeBenefit", back_populates="benefit_type")


class EmployeeDeduction(BaseModel):
    __tablename__ = "employee_deductions"
    __table_args__ = (Index("ix_employee_deductions_employee", "employee_id", "is_active"),)

    business_id       = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id       = Column(Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    deduction_type_id = Column(Uuid, ForeignKey("deduction_types.id", ondelete="CASCADE"), nullable=False)
    amount_override   = Column(Numeric(12, 2), nullable=True)
    is_active         = Column(Boolean, nullable=False, default=True, server_default="true")

    employee        = relationship("Employee")
    deduction_type   = relationship("DeductionType", back_populates="employee_deductions")


class EmployeeBenefit(BaseModel):
    __tablename__ = "employee_benefits"
    __table_args__ = (Index("ix_employee_benefits_employee", "employee_id", "is_active"),)

    business_id     = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id     = Column(Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    benefit_type_id = Column(Uuid, ForeignKey("benefit_types.id", ondelete="CASCADE"), nullable=False)
    amount_override = Column(Numeric(12, 2), nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True, server_default="true")

    employee     = relationship("Employee")
    benefit_type = relationship("BenefitType", back_populates="employee_benefits")


class Timesheet(BaseModel):
    __tablename__ = "timesheets"
    __table_args__ = (Index("ix_timesheets_employee_date", "employee_id", "work_date"),)

    business_id  = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id  = Column(Uuid, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date    = Column(Date, nullable=False)
    hours_worked = Column(Numeric(5, 2), nullable=False)
    notes        = Column(Text, nullable=True)

    employee = relationship("Employee")
