"""API tests for platform-admin LinkedIn lead CSV import + status updates."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.core.security import create_platform_access_token
from app.models.linkedin_lead import LinkedInLead
from app.models.platform_admin import PlatformAdmin

_CSV_HEADER = "Lead ID,First Name,Last Name,Email Address,Company Name,Job Title,Phone Number,Campaign Name,Form Name,Submitted At\n"


def _platform_headers(admin: PlatformAdmin) -> dict[str, str]:
    token = create_platform_access_token(
        {
            "platform_admin_id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "platform_role": admin.platform_role,
            "impersonation_allowed": admin.impersonation_allowed,
            "phash": admin.hashed_password[-8:],
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _csv_row(lead_id: str, first="Jane", last="Doe", email="jane@acme.com") -> str:
    return f"{lead_id},{first},{last},{email},Acme Corp,Ops Manager,+27825550000,Q3 Demo Push,Get a Demo,\n"


class TestImportLinkedInLeadsCsv:
    def test_successful_import_stores_rows_and_notifies(self, client, test_db: Session, platform_admin):
        csv_content = _CSV_HEADER + _csv_row("li-1") + _csv_row("li-2", "John", "Smith", "john@acme.com")

        with patch("app.services.linkedin_leads.send_linkedin_lead_email") as mock_email:
            r = client.post(
                "/platform/v1/linkedin-leads/import",
                headers=_platform_headers(platform_admin),
                files={"file": ("leads.csv", csv_content.encode("utf-8"), "text/csv")},
            )

        assert r.status_code == 201, r.text
        body = r.json()
        assert body["imported"] == 2
        assert body["skipped_duplicates"] == 0
        assert body["errors"] == []
        assert mock_email.call_count == 2

        leads = test_db.query(LinkedInLead).all()
        assert len(leads) == 2
        assert {lead_.ingestion_source for lead_ in leads} == {"csv_import"}
        assert {lead_.status for lead_ in leads} == {"new"}

    def test_duplicate_linkedin_lead_id_is_skipped(self, client, test_db: Session, platform_admin):
        headers = _platform_headers(platform_admin)
        first_csv = _CSV_HEADER + _csv_row("li-dup")
        with patch("app.services.linkedin_leads.send_linkedin_lead_email"):
            client.post(
                "/platform/v1/linkedin-leads/import",
                headers=headers,
                files={"file": ("leads.csv", first_csv.encode("utf-8"), "text/csv")},
            )

        second_csv = _CSV_HEADER + _csv_row("li-dup") + _csv_row("li-new")
        with patch("app.services.linkedin_leads.send_linkedin_lead_email") as mock_email:
            r = client.post(
                "/platform/v1/linkedin-leads/import",
                headers=headers,
                files={"file": ("leads.csv", second_csv.encode("utf-8"), "text/csv")},
            )

        assert r.status_code == 201
        body = r.json()
        assert body["imported"] == 1
        assert body["skipped_duplicates"] == 1
        mock_email.assert_called_once()

        assert test_db.query(LinkedInLead).filter(LinkedInLead.linkedin_lead_id == "li-dup").count() == 1

    def test_malformed_row_is_reported_not_fatal(self, client, test_db: Session, platform_admin):
        good_row = _csv_row("li-good")
        bad_row = ",MissingLeadId,Doe,not-an-email,,,,,,\n"
        csv_content = _CSV_HEADER + bad_row + good_row

        with patch("app.services.linkedin_leads.send_linkedin_lead_email"):
            r = client.post(
                "/platform/v1/linkedin-leads/import",
                headers=_platform_headers(platform_admin),
                files={"file": ("leads.csv", csv_content.encode("utf-8"), "text/csv")},
            )

        assert r.status_code == 201
        body = r.json()
        assert body["imported"] == 1
        assert len(body["errors"]) == 1
        assert test_db.query(LinkedInLead).filter(LinkedInLead.linkedin_lead_id == "li-good").count() == 1

    def test_email_failure_does_not_fail_the_import(self, client, test_db: Session, platform_admin):
        csv_content = _CSV_HEADER + _csv_row("li-1")
        with patch("app.services.linkedin_leads.send_linkedin_lead_email", side_effect=Exception("smtp down")):
            r = client.post(
                "/platform/v1/linkedin-leads/import",
                headers=_platform_headers(platform_admin),
                files={"file": ("leads.csv", csv_content.encode("utf-8"), "text/csv")},
            )

        assert r.status_code == 201
        assert r.json()["imported"] == 1
        assert test_db.query(LinkedInLead).filter(LinkedInLead.linkedin_lead_id == "li-1").first() is not None

    def test_unauthenticated_request_is_rejected(self, client):
        csv_content = _CSV_HEADER + _csv_row("li-1")
        r = client.post(
            "/platform/v1/linkedin-leads/import",
            files={"file": ("leads.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert r.status_code == 401


class TestUpdateLinkedInLead:
    def test_updates_status_and_assigned_to(self, client, test_db: Session, platform_admin):
        headers = _platform_headers(platform_admin)
        csv_content = _CSV_HEADER + _csv_row("li-1")
        with patch("app.services.linkedin_leads.send_linkedin_lead_email"):
            client.post(
                "/platform/v1/linkedin-leads/import",
                headers=headers,
                files={"file": ("leads.csv", csv_content.encode("utf-8"), "text/csv")},
            )
        lead = test_db.query(LinkedInLead).filter(LinkedInLead.linkedin_lead_id == "li-1").first()

        r = client.patch(
            f"/platform/v1/linkedin-leads/{lead.id}",
            headers=headers,
            json={"status": "qualified", "assigned_to": "lehakoe"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "qualified"
        assert body["assigned_to"] == "lehakoe"

    def test_unknown_lead_returns_404(self, client, platform_admin):
        r = client.patch(
            "/platform/v1/linkedin-leads/00000000-0000-0000-0000-000000000000",
            headers=_platform_headers(platform_admin),
            json={"status": "contacted"},
        )
        assert r.status_code == 404

    def test_requires_auth(self, client):
        r = client.patch(
            "/platform/v1/linkedin-leads/00000000-0000-0000-0000-000000000000",
            json={"status": "contacted"},
        )
        assert r.status_code == 401
