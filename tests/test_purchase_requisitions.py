"""Purchase requisition service tests - submit, approve/reject, convert-to-PO, events."""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from app.services.purchase_requisition import PurchaseRequisitionService
from app.schemas.purchase_requisition import PRCreate, PRLineItemCreate, PRStatusUpdate
from app.schemas.auth import CurrentUser


def _make_pr_data(**overrides) -> PRCreate:
    defaults = dict(
        title="Replacement laptop for design team",
        justification="Current laptop can't run the design tools anymore",
        estimated_total=Decimal("15000.00"),
        line_items=[],
    )
    defaults.update(overrides)
    return PRCreate(**defaults)


def _make_line_item(**overrides) -> PRLineItemCreate:
    defaults = dict(
        description="Dell XPS 15 laptop",
        quantity=1,
        estimated_unit_cost=Decimal("15000.00"),
    )
    defaults.update(overrides)
    return PRLineItemCreate(**defaults)


class TestPurchaseRequisitionCreate:
    def test_staff_can_submit(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        assert pr.business_id == staff_user.business_id
        assert pr.status == "pending"
        assert pr.requested_by == staff_user.user_id

    def test_owner_can_submit(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(owner_user.business_id, owner_user, _make_pr_data())

        assert pr is not None

    def test_create_with_line_items(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        data = _make_pr_data(line_items=[_make_line_item()])

        pr = service.create(staff_user.business_id, staff_user, data)

        assert len(pr.line_items) == 1
        assert pr.line_items[0].description == "Dell XPS 15 laptop"

    def test_create_emits_requisition_created_event(self, test_db: Session, staff_user: CurrentUser):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = PurchaseRequisitionService(test_db, event_service=mock_event_service)

        service.create(staff_user.business_id, staff_user, _make_pr_data())

        mock_event_service.create_event.assert_called_once()
        assert mock_event_service.create_event.call_args.kwargs["event_type"] == EventType.PURCHASE_REQUISITION_CREATED


class TestPurchaseRequisitionRead:
    def test_get_pr(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        fetched = service.get(staff_user.business_id, staff_user, pr.id)

        assert fetched is not None
        assert fetched.id == pr.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)

        assert service.get(owner_user.business_id, owner_user, uuid4()) is None

    def test_list_prs(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        service.create(staff_user.business_id, staff_user, _make_pr_data())

        prs, total = service.list(staff_user.business_id, staff_user)

        assert total >= 1


class TestPurchaseRequisitionStatusUpdate:
    def test_owner_can_approve(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        approved = service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="approved"))

        assert approved.status == "approved"
        assert approved.approved_by == owner_user.user_id
        assert approved.approved_at is not None

    def test_manager_can_reject_with_reason(self, test_db: Session, manager_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        rejected = service.update_status(
            manager_user.business_id, manager_user, pr.id,
            PRStatusUpdate(status="rejected", rejection_reason="Not in this quarter's budget"),
        )

        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Not in this quarter's budget"

    def test_staff_cannot_approve(self, test_db: Session, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        with pytest.raises(PermissionError, match="cannot"):
            service.update_status(staff_user.business_id, staff_user, pr.id, PRStatusUpdate(status="approved"))

    def test_cannot_re_decide_already_decided_requisition(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())
        service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="approved"))

        with pytest.raises(ValueError, match="already"):
            service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="rejected"))

    def test_status_update_emits_event(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = PurchaseRequisitionService(test_db, event_service=mock_event_service)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())
        mock_event_service.reset_mock()

        service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="approved"))

        assert mock_event_service.create_event.call_args.kwargs["event_type"] == EventType.PURCHASE_REQUISITION_STATUS_CHANGED


class TestPurchaseRequisitionConvert:
    def test_owner_can_convert_approved_requisition(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        data = _make_pr_data(line_items=[_make_line_item(quantity=2, estimated_unit_cost=Decimal("100.00"))])
        pr = service.create(staff_user.business_id, staff_user, data)
        service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="approved"))

        updated_pr, po = service.convert_to_purchase_order(owner_user.business_id, owner_user, pr.id)

        assert updated_pr.status == "converted"
        assert updated_pr.converted_purchase_order_id == po.id
        assert po.status == "draft"
        assert po.total_cost == Decimal("200.00")
        assert len(po.line_items) == 1
        assert po.line_items[0].quantity_ordered == 2

    def test_cannot_convert_pending_requisition(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        with pytest.raises(ValueError, match="approved"):
            service.convert_to_purchase_order(owner_user.business_id, owner_user, pr.id)

    def test_staff_cannot_convert(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())
        service.update_status(owner_user.business_id, owner_user, pr.id, PRStatusUpdate(status="approved"))

        with pytest.raises(PermissionError, match="cannot"):
            service.convert_to_purchase_order(staff_user.business_id, staff_user, pr.id)


class TestPurchaseRequisitionMultiTenancy:
    def test_pr_not_visible_across_businesses(self, test_db: Session, staff_user: CurrentUser, other_user: CurrentUser):
        service = PurchaseRequisitionService(test_db)
        pr = service.create(staff_user.business_id, staff_user, _make_pr_data())

        assert service.get(staff_user.business_id, staff_user, pr.id) is not None
        assert service.get(other_user.business_id, other_user, pr.id) is None
