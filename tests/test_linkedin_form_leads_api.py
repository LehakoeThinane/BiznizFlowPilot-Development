"""API tests for the public LinkedIn-ads landing page lead form."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.linkedin_lead import LinkedInLead

_VALID_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@acme.com",
    "company": "Acme Corp",
    "job_title": "Operations Manager",
    "utm_source": "linkedin",
    "utm_medium": "cpc",
    "utm_campaign": "q3-demo-push",
}


class TestCreateLinkedInFormLead:
    def test_successful_submission_stores_a_row(self, client, test_db: Session):
        with patch("app.services.linkedin_leads.send_linkedin_lead_email") as mock_email:
            r = client.post("/api/v1/marketing/linkedin-form-leads", json=_VALID_PAYLOAD)

        assert r.status_code == 201
        assert r.json() == {"received": True}

        lead = test_db.query(LinkedInLead).filter(LinkedInLead.email == "jane@acme.com").first()
        assert lead is not None
        assert lead.ingestion_source == "landing_page"
        assert lead.status == "new"
        assert lead.utm_campaign == "q3-demo-push"
        mock_email.assert_called_once()

    def test_invalid_email_is_rejected(self, client, test_db: Session):
        payload = {**_VALID_PAYLOAD, "email": "not-an-email"}
        r = client.post("/api/v1/marketing/linkedin-form-leads", json=payload)
        assert r.status_code == 422

    def test_email_failure_does_not_fail_the_request(self, client, test_db: Session):
        with patch("app.services.linkedin_leads.send_linkedin_lead_email", side_effect=Exception("smtp down")):
            r = client.post("/api/v1/marketing/linkedin-form-leads", json=_VALID_PAYLOAD)

        assert r.status_code == 201
        lead = test_db.query(LinkedInLead).filter(LinkedInLead.email == "jane@acme.com").first()
        assert lead is not None

    def test_missing_required_field_is_rejected(self, client, test_db: Session):
        payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "first_name"}
        r = client.post("/api/v1/marketing/linkedin-form-leads", json=payload)
        assert r.status_code == 422
