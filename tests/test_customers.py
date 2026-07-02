"""Customer tests - CRUD, RBAC, multi-tenant isolation."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.services.customer import CustomerService
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.auth import CurrentUser


class TestCustomerCreate:
    """Test customer creation with RBAC."""

    def test_create_customer_as_owner(self, test_db: Session, owner_user: CurrentUser):
        """Owner can create customers."""
        service = CustomerService(test_db)
        data = CustomerCreate(
            name="Acme Corp",
            email="contact@acme.com",
            phone="+1234567890",
        )

        customer = service.create(owner_user.business_id, owner_user, data)

        assert customer.name == "Acme Corp"
        assert customer.email == "contact@acme.com"
        assert customer.business_id == owner_user.business_id

    def test_create_customer_as_manager(self, test_db: Session, manager_user: CurrentUser):
        """Manager can create customers."""
        service = CustomerService(test_db)
        data = CustomerCreate(name="TechCorp")

        customer = service.create(manager_user.business_id, manager_user, data)

        assert customer.name == "TechCorp"
        assert customer.business_id == manager_user.business_id

    def test_create_customer_as_staff_denied(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot create customers."""
        service = CustomerService(test_db)
        data = CustomerCreate(name="NoAccess")

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)


class TestCustomerRead:
    """Test customer retrieval."""

    def test_get_customer(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """Get customer by ID."""
        service = CustomerService(test_db)

        customer = service.get(owner_user.business_id, owner_user, sample_customer.id)

        assert customer.id == sample_customer.id
        assert customer.name == sample_customer.name

    def test_get_customer_not_found(self, test_db: Session, owner_user: CurrentUser):
        """Get non-existent customer returns None."""
        service = CustomerService(test_db)
        fake_id = uuid4()

        customer = service.get(owner_user.business_id, owner_user, fake_id)

        assert customer is None

    def test_list_customers(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """List customers in business."""
        service = CustomerService(test_db)

        customers, total = service.list(owner_user.business_id, owner_user)

        assert len(customers) >= 1
        assert total >= 1
        assert any(c.id == sample_customer.id for c in customers)

    def test_search_customers_by_name(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """Search customers by name."""
        service = CustomerService(test_db)

        customers, total = service.search(owner_user.business_id, owner_user, "Acme")

        assert total >= 1
        assert any(c.id == sample_customer.id for c in customers)


class TestCustomerUpdate:
    """Test customer update with RBAC."""

    def test_update_customer_as_owner(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """Owner can update customer."""
        service = CustomerService(test_db)
        data = CustomerUpdate(name="Updated Corp")

        customer = service.update(owner_user.business_id, owner_user, sample_customer.id, data)

        assert customer.name == "Updated Corp"

    def test_update_customer_as_manager(self, test_db: Session, manager_user: CurrentUser, sample_customer: Customer):
        """Manager can update customer."""
        service = CustomerService(test_db)
        # Need to ensure customer is in same business
        sample_customer.business_id = manager_user.business_id
        test_db.commit()

        data = CustomerUpdate(phone="+9999999999")
        customer = service.update(manager_user.business_id, manager_user, sample_customer.id, data)

        assert customer.phone == "+9999999999"

    def test_update_customer_as_staff_denied(self, test_db: Session, staff_user: CurrentUser, sample_customer: Customer):
        """Staff cannot update customer."""
        service = CustomerService(test_db)
        sample_customer.business_id = staff_user.business_id
        test_db.commit()

        data = CustomerUpdate(name="Hacked")

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, sample_customer.id, data)


class TestCustomerDelete:
    """Test customer deletion with RBAC."""

    def test_delete_customer_as_owner(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """Owner can delete customer."""
        service = CustomerService(test_db)

        success = service.delete(owner_user.business_id, owner_user, sample_customer.id)

        assert success is True
        assert service.get(owner_user.business_id, owner_user, sample_customer.id) is None

    def test_delete_customer_as_manager_denied(self, test_db: Session, manager_user: CurrentUser, sample_customer: Customer):
        """Manager cannot permanently delete."""
        service = CustomerService(test_db)
        sample_customer.business_id = manager_user.business_id
        test_db.commit()

        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(manager_user.business_id, manager_user, sample_customer.id)

    def test_delete_nonexistent_customer(self, test_db: Session, owner_user: CurrentUser):
        """Delete non-existent customer returns False."""
        service = CustomerService(test_db)
        fake_id = uuid4()

        success = service.delete(owner_user.business_id, owner_user, fake_id)

        assert success is False


class TestCustomerMultiTenancy:
    """Test multi-tenant isolation."""

    def test_customer_isolation_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_customer: Customer):
        """Customer from one business not visible to another."""
        service = CustomerService(test_db)

        # Owner can see their customer
        customer = service.get(owner_user.business_id, owner_user, sample_customer.id)
        assert customer is not None

        # Other business user cannot see it
        customer = service.get(other_user.business_id, other_user, sample_customer.id)
        assert customer is None

    def test_list_only_own_business_customers(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_customer: Customer):
        """List only returns customers from user's business."""
        service = CustomerService(test_db)

        # Owner sees their customer
        customers, total = service.list(owner_user.business_id, owner_user)
        assert any(c.id == sample_customer.id for c in customers)

        # Other user doesn't see it
        customers, total = service.list(other_user.business_id, other_user)
        assert not any(c.id == sample_customer.id for c in customers)
