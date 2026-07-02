"""Finance models — expense categories and expenses."""

from sqlalchemy import Boolean, Column, Date, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ExpenseCategory(BaseModel):
    __tablename__ = "expense_categories"
    __table_args__ = (Index("ix_expense_categories_biz", "business_id"),)

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    expenses = relationship("Expense", back_populates="category")


class Expense(BaseModel):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_biz_date", "business_id", "date"),
        Index("ix_expenses_category", "category_id"),
    )

    business_id = Column(Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Uuid, ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(255), nullable=False)
    vendor = Column(String(150), nullable=True)
    reference = Column(String(100), nullable=True)
    paid_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    category = relationship("ExpenseCategory", back_populates="expenses")
