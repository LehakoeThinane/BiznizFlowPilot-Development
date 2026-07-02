"""Inventory models: locations and stock levels."""

from sqlalchemy import Boolean, Column, Computed, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class InventoryLocation(BaseModel):
    """Warehouses, stores, or virtual locations."""

    __tablename__ = "inventory_locations"
    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_business_location_code"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    location_type = Column(String(50), nullable=False, server_default="warehouse")
    address = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    meta_data = Column("metadata", JSONB, nullable=False, default=dict)

    SAFE_CONTEXT_FIELDS = ("id", "name", "code", "location_type", "is_active")


class StockLevel(BaseModel):
    """Product quantities at specific locations."""

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_product_location_stock"),
        Index(
            "ix_stock_levels_low_stock",
            "location_id",
            "product_id",
            postgresql_where=text("(quantity - reserved) < reorder_point"),
        ),
    )

    product_id = Column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id = Column(
        Uuid, ForeignKey("inventory_locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quantity = Column(Integer, nullable=False, server_default="0")
    reserved = Column(Integer, nullable=False, server_default="0")
    available = Column(Integer, Computed("quantity - reserved", persisted=True), nullable=False)
    reorder_point = Column(Integer, nullable=False, server_default="10")
    reorder_quantity = Column(Integer, nullable=False, server_default="50")
    last_counted_at = Column(DateTime(timezone=True), nullable=True)
    last_counted_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    product = relationship("Product")
    location = relationship("InventoryLocation")

    SAFE_CONTEXT_FIELDS = (
        "id",
        "product_id",
        "location_id",
        "quantity",
        "reserved",
        "available",
        "reorder_point",
        "reorder_quantity",
    )
