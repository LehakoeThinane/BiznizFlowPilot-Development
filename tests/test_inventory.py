"""Inventory service tests - locations, stock adjustment, RBAC."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.inventory import InventoryLocation
from app.models.product import Product
from app.services.inventory import InventoryService
from app.schemas.inventory import LocationCreate, LocationUpdate, StockAdjustment
from app.schemas.auth import CurrentUser


def _make_location_data(**overrides) -> LocationCreate:
    defaults = dict(
        name=f"Location {uuid4().hex[:6]}",
        code=f"LOC-{uuid4().hex[:4]}",
        location_type="warehouse",
        is_active=True,
        meta_data={},
    )
    defaults.update(overrides)
    return LocationCreate(**defaults)


class TestLocationCreate:
    def test_owner_can_create(self, test_db: Session, owner_user: CurrentUser):
        service = InventoryService(test_db)
        data = _make_location_data(name="East Warehouse")

        location = service.create_location(owner_user.business_id, owner_user, data)

        assert location.name == "East Warehouse"
        assert location.business_id == owner_user.business_id

    def test_manager_can_create(self, test_db: Session, manager_user: CurrentUser):
        service = InventoryService(test_db)
        data = _make_location_data(name="West Store")

        location = service.create_location(manager_user.business_id, manager_user, data)

        assert location.name == "West Store"

    def test_staff_cannot_create(self, test_db: Session, staff_user: CurrentUser):
        service = InventoryService(test_db)
        data = _make_location_data()

        with pytest.raises(ValueError, match="Permission denied"):
            service.create_location(staff_user.business_id, staff_user, data)


class TestLocationRead:
    def test_get_location(self, test_db: Session, owner_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)

        location = service.get_location(owner_user.business_id, owner_user, sample_location.id)

        assert location is not None
        assert location.id == sample_location.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = InventoryService(test_db)

        result = service.get_location(owner_user.business_id, owner_user, uuid4())

        assert result is None

    def test_list_locations(self, test_db: Session, owner_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)

        locations, total = service.list_locations(owner_user.business_id, owner_user)

        assert total >= 1
        assert any(loc.id == sample_location.id for loc in locations)


class TestLocationUpdate:
    def test_owner_can_update(self, test_db: Session, owner_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)
        data = LocationUpdate(name="Updated Warehouse")

        location = service.update_location(owner_user.business_id, owner_user, sample_location.id, data)

        assert location.name == "Updated Warehouse"

    def test_staff_cannot_update(self, test_db: Session, staff_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)
        sample_location.business_id = staff_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.update_location(staff_user.business_id, staff_user, sample_location.id, LocationUpdate(name="Hack"))

    def test_update_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = InventoryService(test_db)

        result = service.update_location(owner_user.business_id, owner_user, uuid4(), LocationUpdate(name="Ghost"))

        assert result is None


class TestLocationDelete:
    def test_owner_can_delete(self, test_db: Session, owner_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)

        success = service.delete_location(owner_user.business_id, owner_user, sample_location.id)

        assert success is True
        assert service.get_location(owner_user.business_id, owner_user, sample_location.id) is None

    def test_manager_cannot_delete(self, test_db: Session, manager_user: CurrentUser, sample_location: InventoryLocation):
        service = InventoryService(test_db)
        sample_location.business_id = manager_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.delete_location(manager_user.business_id, manager_user, sample_location.id)


class TestStockAdjustment:
    def test_adjust_creates_stock_if_absent(
        self,
        test_db: Session,
        owner_user: CurrentUser,
        sample_product: Product,
        sample_location: InventoryLocation,
    ):
        service = InventoryService(test_db)
        data = StockAdjustment(
            product_id=sample_product.id,
            location_id=sample_location.id,
            quantity_change=50,
            reason="Initial stock",
        )

        stock = service.adjust_stock(owner_user.business_id, owner_user, data)

        assert stock.quantity == 50

    def test_adjust_accumulates_quantity(
        self,
        test_db: Session,
        owner_user: CurrentUser,
        sample_product: Product,
        sample_location: InventoryLocation,
    ):
        service = InventoryService(test_db)
        base = StockAdjustment(product_id=sample_product.id, location_id=sample_location.id, quantity_change=100, reason="receive")
        service.adjust_stock(owner_user.business_id, owner_user, base)

        delta = StockAdjustment(product_id=sample_product.id, location_id=sample_location.id, quantity_change=-30, reason="sold")
        stock = service.adjust_stock(owner_user.business_id, owner_user, delta)

        assert stock.quantity == 70

    def test_all_roles_can_adjust(
        self,
        test_db: Session,
        staff_user: CurrentUser,
        sample_product: Product,
        sample_location: InventoryLocation,
    ):
        sample_product.business_id = staff_user.business_id
        sample_location.business_id = staff_user.business_id
        test_db.commit()

        service = InventoryService(test_db)
        data = StockAdjustment(
            product_id=sample_product.id,
            location_id=sample_location.id,
            quantity_change=10,
            reason="Staff adjustment",
        )

        stock = service.adjust_stock(staff_user.business_id, staff_user, data)

        assert stock.quantity == 10

    def test_low_stock_event_emitted(
        self,
        test_db: Session,
        owner_user: CurrentUser,
        sample_product: Product,
        sample_location: InventoryLocation,
    ):
        from unittest.mock import MagicMock, call
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = InventoryService(test_db, event_service=mock_event_service)

        # Set quantity below reorder_point (default 10)
        data = StockAdjustment(product_id=sample_product.id, location_id=sample_location.id, quantity_change=5, reason="low")
        service.adjust_stock(owner_user.business_id, owner_user, data)

        event_types = [c.kwargs["event_type"] for c in mock_event_service.create_event.call_args_list]
        assert EventType.STOCK_ADJUSTED in event_types
        assert EventType.STOCK_LOW in event_types
