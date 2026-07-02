"""Product repository - data access layer."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Product repository with business_id filtering.
    
    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Product)

    def get_by_sku(self, business_id: UUID, sku: str) -> Optional[Product]:
        """Get product by SKU within business."""
        return self.db.query(Product).filter(
            Product.business_id == business_id,
            Product.sku == sku,
        ).first()

    def get_by_category(self, business_id: UUID, category: str, skip: int = 0, limit: int = 100) -> list[Product]:
        """Get products by category within business."""
        return self.db.query(Product).filter(
            Product.business_id == business_id,
            Product.category == category,
        ).offset(skip).limit(limit).all()
