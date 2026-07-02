"""Product model for ERP inventory management."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import ENUM, JSONB

from app.models.base import BaseModel


class Product(BaseModel):
    """Physical, digital, or service products."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "sku", name="uq_business_product_sku"),
        Index("ix_products_active", "business_id", "is_active"),
        Index("ix_products_category", "business_id", "category"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    product_type = Column(
        ENUM("physical", "digital", "service", name="product_type", create_type=False),
        nullable=False,
        server_default="physical",
    )
    category = Column(String(100), nullable=True)
    unit_price = Column(Numeric(10, 2), nullable=False)
    cost_price = Column(Numeric(10, 2), nullable=True)
    tax_rate = Column(Numeric(5, 2), nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    track_inventory = Column(Boolean, nullable=False, server_default="true")
    barcode = Column(String(100), nullable=True)
    weight = Column(Numeric(10, 2), nullable=True)
    weight_unit = Column(String(10), nullable=False, server_default="kg")
    dimensions = Column(JSONB, nullable=True)
    meta_data = Column("metadata", JSONB, nullable=False, default=dict)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Workflow context allowlist
    SAFE_CONTEXT_FIELDS = (
        "id",
        "sku",
        "name",
        "product_type",
        "category",
        "unit_price",
        "is_active",
        "track_inventory",
    )
