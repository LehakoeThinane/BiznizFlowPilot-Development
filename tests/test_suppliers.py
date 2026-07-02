"""Supplier service tests - CRUD, RBAC, multi-tenant isolation."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.services.supplier import SupplierService
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.schemas.auth import CurrentUser


def _make_supplier_data(**overrides) -> SupplierCreate:
    defaults = dict(
        name=f"Supplier {uuid4().hex[:6]}",
        email="vendor@example.com",
        is_active=True,
        meta_data={},
    )
    defaults.update(overrides)
    return SupplierCreate(**defaults)


class TestSupplierCreate:
    def test_owner_can_create(self, test_db: Session, owner_user: CurrentUser):
        service = SupplierService(test_db)
        data = _make_supplier_data(name="Best Parts Co")

        supplier = service.create(owner_user.business_id, owner_user, data)

        assert supplier.name == "Best Parts Co"
        assert supplier.business_id == owner_user.business_id

    def test_manager_can_create(self, test_db: Session, manager_user: CurrentUser):
        service = SupplierService(test_db)
        data = _make_supplier_data(name="Parts Plus")

        supplier = service.create(manager_user.business_id, manager_user, data)

        assert supplier.name == "Parts Plus"

    def test_staff_cannot_create(self, test_db: Session, staff_user: CurrentUser):
        service = SupplierService(test_db)
        data = _make_supplier_data()

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)


class TestSupplierRead:
    def test_get_supplier(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)

        supplier = service.get(owner_user.business_id, owner_user, sample_supplier.id)

        assert supplier is not None
        assert supplier.id == sample_supplier.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = SupplierService(test_db)

        result = service.get(owner_user.business_id, owner_user, uuid4())

        assert result is None

    def test_list_suppliers(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)

        suppliers, total = service.list(owner_user.business_id, owner_user)

        assert total >= 1
        assert any(s.id == sample_supplier.id for s in suppliers)


class TestSupplierUpdate:
    def test_owner_can_update(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)
        data = SupplierUpdate(name="Updated Supplier")

        supplier = service.update(owner_user.business_id, owner_user, sample_supplier.id, data)

        assert supplier.name == "Updated Supplier"

    def test_manager_can_update(self, test_db: Session, manager_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)
        sample_supplier.business_id = manager_user.business_id
        test_db.commit()

        supplier = service.update(manager_user.business_id, manager_user, sample_supplier.id, SupplierUpdate(phone="+1111111111"))

        assert supplier.phone == "+1111111111"

    def test_staff_cannot_update(self, test_db: Session, staff_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)
        sample_supplier.business_id = staff_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, sample_supplier.id, SupplierUpdate(name="Hack"))

    def test_update_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = SupplierService(test_db)

        result = service.update(owner_user.business_id, owner_user, uuid4(), SupplierUpdate(name="Ghost"))

        assert result is None


class TestSupplierDelete:
    def test_owner_can_delete(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)

        success = service.delete(owner_user.business_id, owner_user, sample_supplier.id)

        assert success is True
        assert service.get(owner_user.business_id, owner_user, sample_supplier.id) is None

    def test_manager_cannot_delete(self, test_db: Session, manager_user: CurrentUser, sample_supplier: Supplier):
        service = SupplierService(test_db)
        sample_supplier.business_id = manager_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(manager_user.business_id, manager_user, sample_supplier.id)

    def test_delete_nonexistent_returns_false(self, test_db: Session, owner_user: CurrentUser):
        service = SupplierService(test_db)

        success = service.delete(owner_user.business_id, owner_user, uuid4())

        assert success is False


class TestSupplierEventEmission:
    def test_create_emits_event(self, test_db: Session, owner_user: CurrentUser):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = SupplierService(test_db, event_service=mock_event_service)
        data = _make_supplier_data(name="Event Supplier")

        service.create(owner_user.business_id, owner_user, data)

        mock_event_service.create_event.assert_called_once()
        call_kwargs = mock_event_service.create_event.call_args.kwargs
        assert call_kwargs["event_type"] == EventType.SUPPLIER_CREATED

    def test_update_emits_event(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = SupplierService(test_db, event_service=mock_event_service)

        service.update(owner_user.business_id, owner_user, sample_supplier.id, SupplierUpdate(name="Renamed"))

        mock_event_service.create_event.assert_called_once()
        call_kwargs = mock_event_service.create_event.call_args.kwargs
        assert call_kwargs["event_type"] == EventType.SUPPLIER_UPDATED

    def test_delete_emits_event(self, test_db: Session, owner_user: CurrentUser, sample_supplier: Supplier):
        from unittest.mock import MagicMock
        from app.core.enums import EventType

        mock_event_service = MagicMock()
        service = SupplierService(test_db, event_service=mock_event_service)

        service.delete(owner_user.business_id, owner_user, sample_supplier.id)

        mock_event_service.create_event.assert_called_once()
        call_kwargs = mock_event_service.create_event.call_args.kwargs
        assert call_kwargs["event_type"] == EventType.SUPPLIER_DELETED


class TestSupplierMultiTenancy:
    def test_supplier_not_visible_across_businesses(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_supplier: Supplier
    ):
        service = SupplierService(test_db)

        assert service.get(owner_user.business_id, owner_user, sample_supplier.id) is not None
        assert service.get(other_user.business_id, other_user, sample_supplier.id) is None
