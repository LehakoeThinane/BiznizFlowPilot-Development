"""Sales order service tests - CRUD, RBAC, status events."""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

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

        with pytest.raises(ValueError, match="Permission denied"):
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


class TestSalesOrderMultiTenancy:
    def test_order_not_visible_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        service = SalesOrderService(test_db)
        order = service.create(owner_user.business_id, owner_user, _make_order_data())

        assert service.get(owner_user.business_id, owner_user, order.id) is not None
        assert service.get(other_user.business_id, other_user, order.id) is None
