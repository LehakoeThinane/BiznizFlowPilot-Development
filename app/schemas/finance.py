"""Finance schemas."""

from __future__ import annotations

from datetime import date as _Date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)


class ExpenseCategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class ExpenseCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime


class ExpenseCreate(BaseModel):
    category_id: UUID | None = None
    date: _Date
    amount: Decimal
    description: str = Field(..., max_length=500)
    vendor: str | None = Field(None, max_length=150)
    reference: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class ExpenseUpdate(BaseModel):
    category_id: UUID | None = None
    date: _Date | None = None
    amount: Decimal | None = None
    description: str | None = Field(None, max_length=500)
    vendor: str | None = Field(None, max_length=150)
    reference: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=2000)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    category_id: UUID | None
    date: _Date
    amount: Decimal
    description: str
    vendor: str | None
    reference: str | None
    notes: str | None
    category_name: str | None = None
    created_at: datetime


class CategoryTotal(BaseModel):
    name: str
    amount: Decimal


class FinanceSummary(BaseModel):
    period_label: str
    revenue: Decimal
    expenses: Decimal
    net_profit: Decimal
    expense_by_category: list[CategoryTotal]


class ExpenseListResponse(BaseModel):
    items: list[ExpenseOut]
    total: int
    skip: int
    limit: int
