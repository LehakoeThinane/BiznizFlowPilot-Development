"""Inventory service - business logic with auto-event emission."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.inventory import InventoryLocation, StockLevel
from app.repositories.inventory import InventoryLocationRepository, StockLevelRepository
from app.schemas.inventory import LocationCreate, LocationUpdate, StockAdjustment
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


class InventoryService:
    """Inventory service with RBAC and auto-event emission."""

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.location_repo = InventoryLocationRepository(db)
        self.stock_repo = StockLevelRepository(db)
        self._event_service = event_service

    def _emit_event(self, event_type: EventType, business_id: UUID, entity_type: str, entity_id: UUID, actor_id: UUID | None = None, description: str | None = None, data: dict | None = None) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id, event_type=event_type, entity_type=entity_type,
                entity_id=entity_id, actor_id=actor_id, description=description, data=data
            )
        except Exception:
            logger.warning("Failed to emit %s event", event_type.value, exc_info=True)

    # Locations
    def create_location(self, business_id: UUID, current_user: CurrentUser, data: LocationCreate) -> InventoryLocation:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can create locations")
        location = self.location_repo.create(business_id=business_id, **data.model_dump())
        return location

    def get_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID) -> InventoryLocation | None:
        return self.location_repo.get(business_id=business_id, entity_id=location_id)

    def list_locations(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[InventoryLocation], int]:
        return self.location_repo.list(business_id=business_id, skip=skip, limit=limit), self.location_repo.count(business_id=business_id)

    def update_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID, data: LocationUpdate) -> InventoryLocation | None:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can update locations")
        return self.location_repo.update(business_id=business_id, entity_id=location_id, **data.model_dump(exclude_unset=True))

    def delete_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID) -> bool:
        if current_user.role != "owner":
            raise ValueError("Permission denied: Only owner can delete locations")
        return self.location_repo.delete(business_id=business_id, entity_id=location_id)

    # Stock Levels
    def adjust_stock(self, business_id: UUID, current_user: CurrentUser, data: StockAdjustment) -> StockLevel:
        # Check permissions
        if current_user.role not in ["owner", "manager", "staff"]:
            raise ValueError("Permission denied")

        # Verify the location belongs to this business before touching any stock.
        location = self.location_repo.get(business_id=business_id, entity_id=data.location_id)
        if not location:
            raise ValueError("Location not found or access denied")

        # SELECT FOR UPDATE acquires a row-level lock, preventing concurrent
        # adjustments to the same product/location from racing each other.
        stock = (
            self.db.query(StockLevel)
            .filter(
                StockLevel.product_id == data.product_id,
                StockLevel.location_id == data.location_id,
            )
            .with_for_update()
            .first()
        )

        if not stock:
            stock = self.stock_repo.create(
                business_id=business_id,
                product_id=data.product_id,
                location_id=data.location_id,
                quantity=data.quantity_change,
            )
        else:
            new_quantity = stock.quantity + data.quantity_change
            if new_quantity < 0:
                raise ValueError(
                    f"Insufficient stock: adjustment of {data.quantity_change} would result in negative quantity"
                )
            stock = self.stock_repo.update(business_id=business_id, entity_id=stock.id, quantity=new_quantity)

        self._emit_event(
            event_type=EventType.STOCK_ADJUSTED,
            business_id=business_id,
            entity_type="stock_level",
            entity_id=stock.id,
            actor_id=current_user.user_id,
            description=f"Stock adjusted by {data.quantity_change}. Reason: {data.reason}",
            data={"quantity_change": data.quantity_change, "new_quantity": stock.quantity, "reason": data.reason}
        )

        if stock.available < stock.reorder_point:
            self._emit_event(
                event_type=EventType.STOCK_LOW,
                business_id=business_id,
                entity_type="stock_level",
                entity_id=stock.id,
                actor_id=None,
                description="Stock is low and needs reordering",
                data={"available": stock.available, "reorder_point": stock.reorder_point}
            )

        return stock
