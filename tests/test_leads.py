"""Lead tests - CRUD, RBAC, state transitions, multi-tenant isolation."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.customer import Customer
from app.services.lead import LeadService
from app.schemas.lead import LeadCreate, LeadUpdate
from app.schemas.auth import CurrentUser


class TestLeadCreate:
    """Test lead creation with RBAC."""

    def test_create_lead_as_owner(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        """Owner can create leads."""
        service = LeadService(test_db)
        data = LeadCreate(
            customer_id=sample_customer.id,
            status="new",
            source="web_form",
        )

        lead = service.create(owner_user.business_id, owner_user, data)

        assert lead.customer_id == sample_customer.id
        assert lead.status == "new"
        assert lead.business_id == owner_user.business_id

    def test_create_lead_as_manager(self, test_db: Session, manager_user: CurrentUser):
        """Manager can create leads."""
        service = LeadService(test_db)
        data = LeadCreate(status="contacted", source="phone")

        lead = service.create(manager_user.business_id, manager_user, data)

        assert lead.status == "contacted"
        assert lead.business_id == manager_user.business_id

    def test_create_lead_as_staff_denied(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot create leads."""
        service = LeadService(test_db)
        data = LeadCreate()

        with pytest.raises(ValueError, match="Permission denied"):
            service.create(staff_user.business_id, staff_user, data)


class TestLeadStateTransitions:
    """Test lead pipeline state transitions."""

    def test_valid_transition_new_to_contacted(self, test_db: Session, owner_user: CurrentUser, sample_lead: Lead):
        """Valid transition: new → contacted."""
        service = LeadService(test_db)
        data = LeadUpdate(status="contacted")

        lead = service.update(owner_user.business_id, owner_user, sample_lead.id, data)

        assert lead.status == "contacted"

    def test_valid_transition_contacted_to_qualified(self, test_db: Session, owner_user: CurrentUser):
        """Valid transition: contacted → qualified."""
        service = LeadService(test_db)
        lead = service.repo.create(
            business_id=owner_user.business_id,
            status="contacted",
        )
        test_db.commit()

        data = LeadUpdate(status="qualified")
        updated = service.update(owner_user.business_id, owner_user, lead.id, data)

        assert updated.status == "qualified"

    def test_valid_transition_qualified_to_won(self, test_db: Session, owner_user: CurrentUser):
        """Valid transition: qualified → won."""
        service = LeadService(test_db)
        lead = service.repo.create(
            business_id=owner_user.business_id,
            status="qualified",
        )
        test_db.commit()

        data = LeadUpdate(status="won")
        updated = service.update(owner_user.business_id, owner_user, lead.id, data)

        assert updated.status == "won"

    def test_invalid_transition_won_to_contacted(self, test_db: Session, owner_user: CurrentUser):
        """Invalid transition: won → contacted (terminal state)."""
        service = LeadService(test_db)
        lead = service.repo.create(
            business_id=owner_user.business_id,
            status="won",
        )
        test_db.commit()

        data = LeadUpdate(status="contacted")

        with pytest.raises(ValueError, match="Invalid state transition"):
            service.update(owner_user.business_id, owner_user, lead.id, data)

    def test_invalid_transition_new_to_qualified(self, test_db: Session, owner_user: CurrentUser, sample_lead: Lead):
        """Invalid transition: new → qualified (skips contacted)."""
        service = LeadService(test_db)
        data = LeadUpdate(status="qualified")

        with pytest.raises(ValueError, match="Invalid state transition"):
            service.update(owner_user.business_id, owner_user, sample_lead.id, data)


class TestLeadRBAC:
    """Test lead RBAC."""

    def test_owner_sees_all_leads(self, test_db: Session, owner_user: CurrentUser, sample_lead: Lead):
        """Owner sees all leads in business."""
        service = LeadService(test_db)

        leads, total = service.list(owner_user.business_id, owner_user)

        assert total >= 1
        assert any(l.id == sample_lead.id for l in leads)

    def test_manager_sees_all_leads(self, test_db: Session, manager_user: CurrentUser, sample_lead: Lead, owner_user: CurrentUser):
        """Manager sees all leads in business."""
        sample_lead.business_id = manager_user.business_id
        test_db.commit()

        service = LeadService(test_db)
        leads, total = service.list(manager_user.business_id, manager_user)

        assert total >= 1
        assert any(l.id == sample_lead.id for l in leads)

    def test_staff_sees_only_assigned_leads(self, test_db: Session, staff_user: CurrentUser):
        """Staff only sees leads assigned to them."""
        service = LeadService(test_db)

        # Create lead assigned to staff
        lead1 = service.repo.create(
            business_id=staff_user.business_id,
            status="new",
            assigned_to=staff_user.id,
        )
        # Create lead assigned to someone else
        lead2 = service.repo.create(
            business_id=staff_user.business_id,
            status="new",
            assigned_to=uuid4(),
        )
        test_db.commit()

        leads, total = service.list(staff_user.business_id, staff_user)

        assert any(l.id == lead1.id for l in leads)
        assert not any(l.id == lead2.id for l in leads)

    def test_staff_cannot_update_unassigned_lead(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot update leads not assigned to them."""
        service = LeadService(test_db)
        lead = service.repo.create(
            business_id=staff_user.business_id,
            status="new",
            assigned_to=uuid4(),
        )
        test_db.commit()

        data = LeadUpdate(status="contacted")

        with pytest.raises(ValueError, match="Permission denied"):
            service.update(staff_user.business_id, staff_user, lead.id, data)

    def test_staff_can_update_own_lead(self, test_db: Session, staff_user: CurrentUser):
        """Staff can update leads assigned to them."""
        service = LeadService(test_db)
        lead = service.repo.create(
            business_id=staff_user.business_id,
            status="new",
            assigned_to=staff_user.id,
        )
        test_db.commit()

        data = LeadUpdate(status="contacted")
        updated = service.update(staff_user.business_id, staff_user, lead.id, data)

        assert updated.status == "contacted"

    def test_only_manager_can_assign(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser, staff_user: CurrentUser, sample_lead: Lead):
        """Only owner/manager can assign leads."""
        service = LeadService(test_db)

        # Owner can assign
        lead = service.assign(owner_user.business_id, owner_user, sample_lead.id, uuid4())
        test_db.commit()
        assert lead.assigned_to is not None

        # Manager can assign (with their business)
        sample_lead.business_id = manager_user.business_id
        test_db.commit()
        lead = service.assign(manager_user.business_id, manager_user, sample_lead.id, uuid4())
        assert lead.assigned_to is not None

        # Staff cannot assign
        with pytest.raises(ValueError, match="Permission denied"):
            service.assign(staff_user.business_id, staff_user, sample_lead.id, uuid4())


class TestLeadDeletion:
    """Test lead deletion."""

    def test_only_owner_can_delete(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser, staff_user: CurrentUser, sample_lead: Lead):
        """Only owner can permanently delete leads."""
        service = LeadService(test_db)

        # Owner can delete
        success = service.delete(owner_user.business_id, owner_user, sample_lead.id)
        assert success is True

        # Manager cannot delete
        lead2 = service.repo.create(business_id=manager_user.business_id)
        test_db.commit()
        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(manager_user.business_id, manager_user, lead2.id)

        # Staff cannot delete
        lead3 = service.repo.create(business_id=staff_user.business_id)
        test_db.commit()
        with pytest.raises(ValueError, match="Permission denied"):
            service.delete(staff_user.business_id, staff_user, lead3.id)


class TestLeadMultiTenancy:
    """Test multi-tenant isolation."""

    def test_lead_isolation_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser, sample_lead: Lead):
        """Lead from one business not visible to another."""
        service = LeadService(test_db)

        # Owner can see their lead
        lead = service.get(owner_user.business_id, owner_user, sample_lead.id)
        assert lead is not None

        # Other business cannot see it
        lead = service.get(other_user.business_id, other_user, sample_lead.id)
        assert lead is None
