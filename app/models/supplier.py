"""Supplier model for ERP purchasing."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class Supplier(BaseModel):
    """Vendors and suppliers for purchasing."""

    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_business_supplier_code"),
        Index("ix_suppliers_active", "business_id", "is_active"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    address = Column(JSONB, nullable=True)
    payment_terms = Column(String(100), nullable=True)
    tax_id = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    rating = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    meta_data = Column("metadata", JSONB, nullable=False, default=dict)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    SAFE_CONTEXT_FIELDS = (
        "id",
        "name",
        "code",
        "email",
        "phone",
        "payment_terms",
        "is_active",
        "rating",
    )
