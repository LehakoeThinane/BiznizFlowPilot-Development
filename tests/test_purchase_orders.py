"""Purchase order service tests - CRUD, RBAC, status events."""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.purchase_order import PurchaseOrderService
from app.schemas.purchase_order import POCreate, POLineItemCreate, POUpdate
from app.schemas.auth import CurrentUser


def _make_po_data(**overrides) -> POCreate:
    defaults = dict(
        po_number=f"PO-{uuid4().hex[:8].upper()}",
        status="draft",
        total_cost=Decimal("500.00"),
        meta_data={},
        line_items=[],
    )
    defaults.update(overrides)
    return POCreate(**defaults)


def _make_line_item() -> POLineItemCreate:
    return POLineItemCreate(
        quantity_ordered=10,
        unit_cost=Decimal("50.00"),
        subtotal=Decimal("500.00"),
    )


class TestPurchaseOrderCreate:
    def test_owner_can_create(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        data = _make_po_data()

        po = service.create(owner_user.business_id, owner_user, data)

        assert po.business_id == owner_user.business_id
        assert po.status == "draft"

    def test_manager_can_create(self, test_db: Session, manager_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        data = _make_po_data()

        po = service.create(manager_user.business_id, manager_user, data)

        assert po is not None

    def test_staff_cannot_create(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        data = _make_po_data()

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)

    def test_create_with_line_items(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        data = _make_po_data(line_items=[_make_line_item(), _make_line_item()])

        po = service.create(owner_user.business_id, owner_user, data)

        assert len(po.line_items) == 2

    def test_create_emits_purchase_order_created_event(self, test_db: Session, owner_user: CurrentUser):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = PurchaseOrderService(test_db, event_service=mock_event_service)
        data = _make_po_data()

        service.create(owner_user.business_id, owner_user, data)

        mock_event_service.create_event.assert_called_once()
        assert mock_event_service.create_event.call_args.kwargs["event_type"] == EventType.PURCHASE_ORDER_CREATED


class TestPurchaseOrderRead:
    def test_get_po(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        po = service.create(owner_user.business_id, owner_user, _make_po_data())

        fetched = service.get(owner_user.business_id, owner_user, po.id)

        assert fetched is not None
        assert fetched.id == po.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)

        result = service.get(owner_user.business_id, owner_user, uuid4())

        assert result is None

    def test_list_pos(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        service.create(owner_user.business_id, owner_user, _make_po_data())

        pos, total = service.list(owner_user.business_id, owner_user)

        assert total >= 1


class TestPurchaseOrderUpdate:
    def test_owner_can_update_status(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        po = service.create(owner_user.business_id, owner_user, _make_po_data())

        updated = service.update(owner_user.business_id, owner_user, po.id, POUpdate(status="sent"))

        assert updated.status == "sent"

    def test_manager_can_update(self, test_db: Session, manager_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        po = service.create(manager_user.business_id, manager_user, _make_po_data())

        updated = service.update(manager_user.business_id, manager_user, po.id, POUpdate(status="sent"))

        assert updated.status == "sent"

    def test_staff_cannot_update(self, test_db: Session, staff_user: CurrentUser):
        # Staff can't create POs, so we need to create as owner then reassign
        from app.models.purchase_order import PurchaseOrder
        po_obj = PurchaseOrder(
            id=uuid4(),
            business_id=staff_user.business_id,
            po_number=f"PO-{uuid4().hex[:8].upper()}",
            status="draft",
            total_cost=100,
            meta_data={},
        )
        test_db.add(po_obj)
        test_db.commit()

        service = PurchaseOrderService(test_db)

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, po_obj.id, POUpdate(status="sent"))

    def test_update_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseOrderService(test_db)

        result = service.update(owner_user.business_id, owner_user, uuid4(), POUpdate(status="sent"))

        assert result is None


class TestPurchaseOrderStatusEvents:
    @pytest.mark.parametrize("new_status,expected_event", [
        ("sent", "purchase_order_sent"),
        ("received", "purchase_order_received"),
    ])
    def test_status_change_emits_correct_event(
        self, test_db: Session, owner_user: CurrentUser, new_status: str, expected_event: str
    ):
        from unittest.mock import MagicMock

        mock_event_service = MagicMock()
        service = PurchaseOrderService(test_db, event_service=mock_event_service)
        po = service.create(owner_user.business_id, owner_user, _make_po_data())
        mock_event_service.reset_mock()

        service.update(owner_user.business_id, owner_user, po.id, POUpdate(status=new_status))

        emitted = mock_event_service.create_event.call_args.kwargs["event_type"].value
        assert emitted == expected_event


class TestPurchaseOrderMultiTenancy:
    def test_po_not_visible_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        service = PurchaseOrderService(test_db)
        po = service.create(owner_user.business_id, owner_user, _make_po_data())

        assert service.get(owner_user.business_id, owner_user, po.id) is not None
        assert service.get(other_user.business_id, other_user, po.id) is None
