"""Product service tests - CRUD, RBAC, multi-tenant isolation."""

import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.product import ProductService
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.auth import CurrentUser


def _make_product_data(**overrides) -> ProductCreate:
    defaults = dict(
        sku=f"SKU-{uuid4().hex[:6]}",
        name="Widget Pro",
        product_type="physical",
        unit_price=Decimal("49.99"),
        tax_rate=Decimal("0.00"),
        weight_unit="kg",
        meta_data={},
    )
    defaults.update(overrides)
    return ProductCreate(**defaults)


class TestProductCreate:
    def test_owner_can_create(self, test_db: Session, owner_user: CurrentUser):
        service = ProductService(test_db)
        data = _make_product_data(name="Gadget X")

        product = service.create(owner_user.business_id, owner_user, data)

        assert product.name == "Gadget X"
        assert product.business_id == owner_user.business_id

    def test_manager_can_create(self, test_db: Session, manager_user: CurrentUser):
        service = ProductService(test_db)
        data = _make_product_data(name="Gadget Y")

        product = service.create(manager_user.business_id, manager_user, data)

        assert product.name == "Gadget Y"

    def test_staff_cannot_create(self, test_db: Session, staff_user: CurrentUser):
        service = ProductService(test_db)
        data = _make_product_data()

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)


class TestProductRead:
    def test_get_product(self, test_db: Session, owner_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)

        product = service.get(owner_user.business_id, owner_user, sample_product.id)

        assert product is not None
        assert product.id == sample_product.id

    def test_get_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = ProductService(test_db)

        product = service.get(owner_user.business_id, owner_user, uuid4())

        assert product is None

    def test_list_products(self, test_db: Session, owner_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)

        products, total = service.list(owner_user.business_id, owner_user)

        assert total >= 1
        assert any(p.id == sample_product.id for p in products)


class TestProductUpdate:
    def test_owner_can_update(self, test_db: Session, owner_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)
        data = ProductUpdate(name="Updated Widget")

        product = service.update(owner_user.business_id, owner_user, sample_product.id, data)

        assert product.name == "Updated Widget"

    def test_manager_can_update(self, test_db: Session, manager_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)
        sample_product.business_id = manager_user.business_id
        test_db.commit()

        product = service.update(manager_user.business_id, manager_user, sample_product.id, ProductUpdate(name="Mgr Update"))

        assert product.name == "Mgr Update"

    def test_staff_cannot_update(self, test_db: Session, staff_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)
        sample_product.business_id = staff_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, sample_product.id, ProductUpdate(name="Hack"))

    def test_update_nonexistent_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = ProductService(test_db)

        result = service.update(owner_user.business_id, owner_user, uuid4(), ProductUpdate(name="Ghost"))

        assert result is None


class TestProductDelete:
    def test_owner_can_delete(self, test_db: Session, owner_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)

        success = service.delete(owner_user.business_id, owner_user, sample_product.id)

        assert success is True
        assert service.get(owner_user.business_id, owner_user, sample_product.id) is None

    def test_manager_cannot_delete(self, test_db: Session, manager_user: CurrentUser, sample_product: Product):
        service = ProductService(test_db)
        sample_product.business_id = manager_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(manager_user.business_id, manager_user, sample_product.id)

    def test_delete_nonexistent_returns_false(self, test_db: Session, owner_user: CurrentUser):
        service = ProductService(test_db)

        success = service.delete(owner_user.business_id, owner_user, uuid4())

        assert success is False


class TestProductMultiTenancy:
    def test_product_not_visible_across_businesses(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_product: Product
    ):
        service = ProductService(test_db)

        assert service.get(owner_user.business_id, owner_user, sample_product.id) is not None
        assert service.get(other_user.business_id, other_user, sample_product.id) is None

    def test_list_only_own_business(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_product: Product
    ):
        service = ProductService(test_db)

        own_products, _ = service.list(owner_user.business_id, owner_user)
        other_products, _ = service.list(other_user.business_id, other_user)

        assert any(p.id == sample_product.id for p in own_products)
        assert not any(p.id == sample_product.id for p in other_products)
