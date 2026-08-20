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


@pytest.fixture(autouse=True)
def _no_real_email_scraping():
    """Email enrichment makes a real HTTP request per website - stub it out
    by default so these tests don't hit the network. Tests that care about
    the enrichment behavior override this with their own patch."""
    with patch("app.services.lead_gen.find_email", return_value=None):
        yield


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
            assert lead.source == "google_places_has_website"
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


class TestLeadGenServiceAngle:
    """`source` encodes which pitch fits - "no website" is the cleanest,
    free signal Places gives for "they need a site built"; having one
    means a different pitch (systems/automation), not a worse lead."""

    def test_no_website_result_tagged_for_website_pitch(self, test_db: Session, owner_user: CurrentUser):
        no_website = PlaceResult(
            place_id="place_no_site", name="No Website Co", address="1 Main St",
            phone="011 0000000", website=None,
        )

        with patch("app.services.lead_gen.search_text", return_value=[no_website]):
            result = LeadGenService(test_db).find_via_google_places(
                owner_user.business_id, owner_user, query="hardware stores"
            )

        assert result.leads[0].source == "google_places_no_website"
        assert "new site build" in result.leads[0].notes

    def test_has_website_result_tagged_for_systems_pitch(self, test_db: Session, owner_user: CurrentUser):
        has_website = PlaceResult(
            place_id="place_has_site", name="Has Website Co", address="1 Main St",
            phone="011 0000000", website="https://example.co.za",
        )

        with patch("app.services.lead_gen.search_text", return_value=[has_website]):
            result = LeadGenService(test_db).find_via_google_places(
                owner_user.business_id, owner_user, query="hardware stores"
            )

        assert result.leads[0].source == "google_places_has_website"
        assert "systems/automation review" in result.leads[0].notes


class TestLeadGenQualificationScoring:
    def test_strong_result_is_auto_qualified(self, test_db: Session, owner_user: CurrentUser):
        strong = PlaceResult(
            place_id="place_strong", name="Acme Plumbing", address="1 Main St",
            phone="0110000000", website="https://acme-plumbing.co.za",
            types=["plumber"], rating=4.7, user_rating_count=85,
        )

        with patch("app.services.lead_gen.search_text", return_value=[strong]):
            result = LeadGenService(test_db).find_via_google_places(
                owner_user.business_id, owner_user, query="plumbers in Johannesburg"
            )

        assert len(result.leads) == 1
        assert result.leads[0].status == "qualified"
        assert result.qualified_count == 1
        assert "score" in result.leads[0].notes.lower()

    def test_weak_result_stays_new_not_qualified(self, test_db: Session, owner_user: CurrentUser):
        weak = PlaceResult(
            place_id="place_weak", name="Random Co", address="1 Main St",
            phone="0110000000", website=None,
        )

        with patch("app.services.lead_gen.search_text", return_value=[weak]):
            result = LeadGenService(test_db).find_via_google_places(
                owner_user.business_id, owner_user, query="plumbers in Johannesburg"
            )

        assert len(result.leads) == 1
        assert result.leads[0].status == "new"
        assert result.qualified_count == 0

    def test_closed_business_is_excluded_entirely(self, test_db: Session, owner_user: CurrentUser):
        closed = PlaceResult(
            place_id="place_closed", name="Defunct Plumbing", address="1 Main St",
            phone="0110000000", website="https://defunct.co.za",
            business_status="CLOSED_PERMANENTLY", rating=4.9, user_rating_count=200, types=["plumber"],
        )

        with patch("app.services.lead_gen.search_text", return_value=[closed]):
            result = LeadGenService(test_db).find_via_google_places(
                owner_user.business_id, owner_user, query="plumbers"
            )

        assert len(result.leads) == 0
        assert result.skipped_closed == 1
        customer = test_db.query(Customer).filter(Customer.external_ref == "google_places:place_closed").first()
        assert customer is None


class TestLeadGenEmailEnrichment:
    def test_scraped_email_lands_on_customer(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)), \
             patch("app.services.lead_gen.find_email", return_value="info@plumbing0.co.za"):
            service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")

        customer = test_db.query(Customer).filter(Customer.external_ref == "google_places:place_0").first()
        assert customer.email == "info@plumbing0.co.za"

    def test_no_email_found_leaves_customer_email_null(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)), \
             patch("app.services.lead_gen.find_email", return_value=None):
            service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")

        customer = test_db.query(Customer).filter(Customer.external_ref == "google_places:place_0").first()
        assert customer.email is None

    def test_result_without_website_skips_scraping(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenService(test_db)
        no_website = PlaceResult(
            place_id="place_no_site", name="No Website Co", address="1 Main St",
            phone="011 0000000", website=None,
        )

        with patch("app.services.lead_gen.search_text", return_value=[no_website]), \
             patch("app.services.lead_gen.find_email") as mock_find_email:
            service.find_via_google_places(owner_user.business_id, owner_user, query="plumbers")

        mock_find_email.assert_not_called()
