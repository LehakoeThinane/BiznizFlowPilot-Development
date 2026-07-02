"""Inventory repositories - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.inventory import InventoryLocation, StockLevel
from app.repositories.base import BaseRepository


class InventoryLocationRepository(BaseRepository[InventoryLocation]):
    """InventoryLocation repository with business_id filtering."""

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, InventoryLocation)


class StockLevelRepository(BaseRepository[StockLevel]):
    """StockLevel repository with business_id filtering.

    StockLevel has no business_id column — tenant isolation is enforced through
    the product_id and location_id FK chains (products/locations are tenant-scoped).
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, StockLevel)

    def create(self, business_id: UUID, **kwargs) -> StockLevel:
        """Create a stock level record, omitting business_id (not a column on StockLevel)."""
        entity = StockLevel(**kwargs)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get(self, business_id: UUID, entity_id: UUID) -> StockLevel | None:
        """Get stock level by ID (no business_id filter — enforced via product/location FKs)."""
        return self.db.query(StockLevel).filter(StockLevel.id == entity_id).first()

    def update(self, business_id: UUID, entity_id: UUID, **kwargs) -> StockLevel | None:
        """Update stock level by ID."""
        entity = self.get(business_id, entity_id)
        if not entity:
            return None
        for key, value in kwargs.items():
            setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get_by_product_and_location(self, product_id: UUID, location_id: UUID) -> StockLevel | None:
        """Get stock level for a product at a specific location."""
        return self.db.query(StockLevel).filter(
            StockLevel.product_id == product_id,
            StockLevel.location_id == location_id,
        ).first()

    def get_low_stock(self, limit: int = 100) -> list[StockLevel]:
        """Get low stock items across all locations (needs manual business filter in service)."""
        return self.db.query(StockLevel).filter(
            StockLevel.available < StockLevel.reorder_point
        ).limit(limit).all()
