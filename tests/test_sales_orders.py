"""Sales order service tests - CRUD, RBAC, status events."""

import pytest
from decimal import Decimal
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.inventory import InventoryLocation, StockLevel
from app.models.product import Product
from app.models.sales_order import SalesOrder
from app.services.sales_order import SalesOrderService
from app.schemas.sales_order import LineItemCreate, OrderCreate, OrderUpdate
from app.schemas.auth import CurrentUser


def _make_order_data(**overrides) -> OrderCreate:
    defaults = dict(
        order_number=f"SO-{uuid4().hex[:8].upper()}",
        status="draft",
        total_amount=Decimal("100.00"),
        meta_data={},
        line_items=[],
    )
    defaults.update(overrides)
    return OrderCreate(**defaults)


def _make_line_item() -> LineItemCreate:
    return LineItemCreate(
        quantity=2,
        unit_price=Decimal("50.00"),
        subtotal=Decimal("100.00"),
    )


class TestSalesOrderCreate:
    def test_owner_can_create(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)
        data = _make_order_data()

        order = service.create(owner_user.business_id, owner_user, data)

        assert order.business_id == owner_user.business_id
        assert order.status == "draft"

    def test_manager_can_create(self, test_db: Session, manager_user: CurrentUser):
        service = SalesOrderService(test_db)
        data = _make_order_data()

        order = service.create(manager_user.business_id, manager_user, data)

        assert order is not None

    def test_staff_can_create(self, test_db: Session, staff_user: CurrentUser):
        service = SalesOrderService(test_db)
        data = _make_order_data()

        order = service.create(staff_user.business_id, staff_user, data)

        assert order is not None

    def test_create_with_line_items(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)
        data = _make_order_data(line_items=[_make_line_item(), _make_line_item()])

        order = service.create(owner_user.business_id, owner_user, data)

        assert len(order.line_items) == 2

    def test_create_emits_order_created_event(self, test_db: Session, owner_user: CurrentUser):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = SalesOrderService(test_db, event_service=mock_event_service)
        data = _make_order_data()

        service.create(owner_user.business_id, owner_user, data)

        mock_event_service.create_event.assert_called_once()
        assert mock_event_service.create_event.call_args.kwargs["event_type"] == EventType.ORDER_CREATED


class TestSalesOrderRead:
    def test_get_order(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(owner_user.business_id, owner_user, _make_order_data())

        fetched = service.get(owner_user.business_id, owner_user, order.id)

        assert fetched is not None
        assert fetched.id == order.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)

        result = service.get(owner_user.business_id, owner_user, uuid4())

        assert result is None

    def test_list_orders(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)
        service.create(owner_user.business_id, owner_user, _make_order_data())

        orders, total = service.list(owner_user.business_id, owner_user)

        assert total >= 1


class TestSalesOrderUpdate:
    def test_owner_can_update_status(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(owner_user.business_id, owner_user, _make_order_data())

        updated = service.update(owner_user.business_id, owner_user, order.id, OrderUpdate(status="confirmed"))

        assert updated.status == "confirmed"

    def test_manager_can_update(self, test_db: Session, manager_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(manager_user.business_id, manager_user, _make_order_data())

        updated = service.update(manager_user.business_id, manager_user, order.id, OrderUpdate(status="confirmed"))

        assert updated.status == "confirmed"

    def test_staff_cannot_update(self, test_db: Session, staff_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(staff_user.business_id, staff_user, _make_order_data())

        with pytest.raises(PermissionError, match="cannot"):
            service.update(staff_user.business_id, staff_user, order.id, OrderUpdate(status="confirmed"))

    def test_update_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = SalesOrderService(test_db)

        result = service.update(owner_user.business_id, owner_user, uuid4(), OrderUpdate(status="confirmed"))

        assert result is None


class TestSalesOrderStatusEvents:
    @pytest.mark.parametrize("new_status,expected_event", [
        ("confirmed", "order_confirmed"),
        ("shipped", "order_shipped"),
        ("delivered", "order_delivered"),
        ("cancelled", "order_cancelled"),
    ])
    def test_status_change_emits_correct_event(
        self, test_db: Session, owner_user: CurrentUser, new_status: str, expected_event: str
    ):
        from unittest.mock import MagicMock

        mock_event_service = MagicMock()
        service = SalesOrderService(test_db, event_service=mock_event_service)
        order = service.create(owner_user.business_id, owner_user, _make_order_data())
        mock_event_service.reset_mock()

        service.update(owner_user.business_id, owner_user, order.id, OrderUpdate(status=new_status))

        emitted = mock_event_service.create_event.call_args.kwargs["event_type"].value
        assert emitted == expected_event


def _make_stock(test_db: Session, product: Product, location: InventoryLocation, quantity: int, reserved: int = 0) -> StockLevel:
    stock = StockLevel(
        id=uuid4(),
        product_id=product.id,
        location_id=location.id,
        quantity=quantity,
        reserved=reserved,
    )
    test_db.add(stock)
    test_db.commit()
    test_db.refresh(stock)
    return stock


class TestStockReservation:
    """Stock reservation is the authoritative, lock-protected check - not
    just the earlier _validate_stock pre-check - so it must reject an
    over-quantity reservation even when called directly."""

    def test_reserve_within_stock_succeeds(
        self, test_db: Session, owner_user: CurrentUser, sample_product: Product, sample_location: InventoryLocation
    ):
        _make_stock(test_db, sample_product, sample_location, quantity=10)
        service = SalesOrderService(test_db)
        data = _make_order_data(line_items=[
            LineItemCreate(product_id=sample_product.id, quantity=4, unit_price=Decimal("50.00"), subtotal=Decimal("200.00"))
        ])

        order = service.create(owner_user.business_id, owner_user, data)

        stock = test_db.query(StockLevel).filter(StockLevel.product_id == sample_product.id).first()
        assert order is not None
        assert stock.reserved == 4
        assert stock.available == 6

    def test_reserve_more_than_available_raises_even_if_prevalidation_is_bypassed(
        self, test_db: Session, owner_user: CurrentUser, sample_product: Product, sample_location: InventoryLocation
    ):
        """Simulates the race: by the time _reserve_stock takes its lock, less
        stock is available than an earlier read (_validate_stock) assumed."""
        _make_stock(test_db, sample_product, sample_location, quantity=5)
        service = SalesOrderService(test_db)

        with pytest.raises(HTTPException) as exc_info:
            service._reserve_stock(owner_user.business_id, sample_product.id, 999)

        assert exc_info.value.status_code == 400

        stock = test_db.query(StockLevel).filter(StockLevel.product_id == sample_product.id).first()
        assert stock.reserved == 0  # rejected reservation must not partially allocate

    def test_reserve_allocates_across_multiple_locations(
        self, test_db: Session, owner_user: CurrentUser, sample_product: Product, sample_location: InventoryLocation
    ):
        second_location = InventoryLocation(
            id=uuid4(), business_id=sample_location.business_id, name="Overflow", code="WH-02",
            location_type="warehouse", is_active=True, meta_data={},
        )
        test_db.add(second_location)
        test_db.commit()
        _make_stock(test_db, sample_product, sample_location, quantity=3)
        _make_stock(test_db, sample_product, second_location, quantity=10)
        service = SalesOrderService(test_db)

        service._reserve_stock(owner_user.business_id, sample_product.id, 8)

        total_reserved = sum(
            s.reserved for s in test_db.query(StockLevel).filter(StockLevel.product_id == sample_product.id).all()
        )
        assert total_reserved == 8

    def test_release_stock_restores_availability(
        self, test_db: Session, owner_user: CurrentUser, sample_product: Product, sample_location: InventoryLocation
    ):
        _make_stock(test_db, sample_product, sample_location, quantity=10, reserved=6)
        service = SalesOrderService(test_db)

        service._release_stock(owner_user.business_id, sample_product.id, 4)
        test_db.commit()

        stock = test_db.query(StockLevel).filter(StockLevel.product_id == sample_product.id).first()
        assert stock.reserved == 2
        assert stock.available == 8


class TestSalesOrderMultiTenancy:
    def test_order_not_visible_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(owner_user.business_id, owner_user, _make_order_data())

        assert service.get(owner_user.business_id, owner_user, order.id) is not None
        assert service.get(other_user.business_id, other_user, order.id) is None
