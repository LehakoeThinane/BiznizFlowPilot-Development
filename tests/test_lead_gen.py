"""Lead-gen service tests - Google Places search, dedup, RBAC, notification."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.integrations.google_places import PlaceResult
from app.models.customer import Customer
from app.models.notification import Notification
from app.schemas.auth import CurrentUser
from app.services.lead_gen import LeadGenService


def _fake_places(n: int = 2) -> list[PlaceResult]:
    return [
        PlaceResult(
            place_id=f"place_{i}",
            name=f"Test Plumbing {i}",
            address=f"{i} Main St, Johannesburg",
            phone=f"011 000 000{i}",
            website=f"https://plumbing{i}.co.za",
        )
        for i in range(n)
    ]


class TestLeadGenGooglePlaces:
    def test_owner_creates_leads_from_search_results(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(2)):
            result = service.find_via_google_places(
                owner_user.business_id, owner_user, query="plumbers in Johannesburg"
            )

        assert len(result.leads) == 2
        assert result.skipped_duplicates == 0
        for lead in result.leads:
            assert lead.source == "google_places"
            assert lead.status == "new"

    def test_creates_a_customer_with_external_ref_per_result(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)):
            service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")

        customer = test_db.query(Customer).filter(Customer.external_ref == "google_places:place_0").first()
        assert customer is not None
        assert customer.name == "Test Plumbing 0"
        assert customer.website == "https://plumbing0.co.za"

    def test_repeated_search_skips_already_imported_places(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(2)):
            first = service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")
            second = service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")

        assert len(first.leads) == 2
        assert len(second.leads) == 0
        assert second.skipped_duplicates == 2

    def test_staff_cannot_trigger_lead_gen(self, test_db: Session, staff_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)):
            with pytest.raises(PermissionError, match="cannot"):
                service.find_via_google_places(staff_user.business_id, staff_user, query="plumbers")

    def test_assigned_result_notifies_the_assignee(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)):
            result = service.find_via_google_places(
                owner_user.business_id, owner_user, query="plumbers", assign_to=staff_user.user_id
            )

        notif = (
            test_db.query(Notification)
            .filter(Notification.related_id == result.leads[0].id, Notification.user_id == staff_user.user_id)
            .first()
        )
        assert notif is not None
