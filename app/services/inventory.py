"""Inventory service - business logic with auto-event emission."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.entitlements import FULL_ACCESS_TIERS, LOCATION_LIMITS
from app.core.enums import EventType
from app.core.permissions import ALL_BUSINESS_ROLES, OWNER_ONLY, PRIVILEGED_ROLES, require_role
from app.models.inventory import InventoryLocation, StockLevel
from app.repositories.business import BusinessRepository
from app.repositories.inventory import InventoryLocationRepository, StockLevelRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.inventory import LocationCreate, LocationUpdate, StockAdjustment
from app.schemas.auth import CurrentUser


class InventoryService:
    """Inventory service with RBAC and auto-event emission."""

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.location_repo = InventoryLocationRepository(db)
        self.stock_repo = StockLevelRepository(db)
        self._event_service = event_service

    def _emit_event(self, event_type: EventType, business_id: UUID, entity_type: str, entity_id: UUID, actor_id: UUID | None = None, description: str | None = None, data: dict | None = None) -> None:
        """Queue an event row in the same (not-yet-committed) transaction as
        the caller's pending business-row change - the caller commits once,
        after this call, so both persist atomically or neither does."""
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id, event_type=event_type, entity_type=entity_type,
            entity_id=entity_id, actor_id=actor_id, description=description, data=data,
            commit=False,
        )

    # Locations
    def create_location(self, business_id: UUID, current_user: CurrentUser, data: LocationCreate) -> InventoryLocation:
        require_role(current_user, PRIVILEGED_ROLES, "create locations")

        business = BusinessRepository(self.db).get_by_id(business_id)
        org = OrganizationRepository(self.db).get_by_id(business.organization_id) if business else None
        location_limit = None if org is None or org.plan_tier in FULL_ACCESS_TIERS else LOCATION_LIMITS.get(org.plan_tier)
        if location_limit is not None and self.location_repo.count(business_id=business_id) >= location_limit:
            raise PermissionError("Upgrade your plan to add another inventory location.")

        location = self.location_repo.create(business_id=business_id, **data.model_dump())
        return location

    def get_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID) -> InventoryLocation | None:
        return self.location_repo.get(business_id=business_id, entity_id=location_id)

    def list_locations(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[InventoryLocation], int]:
        return self.location_repo.list(business_id=business_id, skip=skip, limit=limit), self.location_repo.count(business_id=business_id)

    def update_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID, data: LocationUpdate) -> InventoryLocation | None:
        require_role(current_user, PRIVILEGED_ROLES, "update locations")
        return self.location_repo.update(business_id=business_id, entity_id=location_id, **data.model_dump(exclude_unset=True))

    def delete_location(self, business_id: UUID, current_user: CurrentUser, location_id: UUID) -> bool:
        require_role(current_user, OWNER_ONLY, "delete locations")
        return self.location_repo.delete(business_id=business_id, entity_id=location_id)

    # Stock Levels
    def adjust_stock(self, business_id: UUID, current_user: CurrentUser, data: StockAdjustment) -> StockLevel:
        require_role(current_user, ALL_BUSINESS_ROLES, "adjust stock")

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
                commit=False,
            )
        else:
            new_quantity = stock.quantity + data.quantity_change
            if new_quantity < 0:
                raise ValueError(
                    f"Insufficient stock: adjustment of {data.quantity_change} would result in negative quantity"
                )
            stock = self.stock_repo.update(business_id=business_id, entity_id=stock.id, quantity=new_quantity, commit=False)

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

        self.db.commit()
        self.db.refresh(stock)
        return stock
