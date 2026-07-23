"""API-level tests for the public marketing-site gated guide download route."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.marketing_guide_lead import MarketingGuideLead

_VALID_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@acme.com",
    "company": "Acme Corp",
    "guide_slug": "crm-sales-pipeline",
    "source_page": "/biznizflowpilot",
    "consented": True,
}


class TestCreateGuideLead:
    def test_successful_submission_stores_a_row(self, client, test_db: Session):
        with patch("app.api.marketing_leads.send_marketing_guide_lead_email") as mock_email:
            r = client.post("/api/v1/marketing/guide-leads", json=_VALID_PAYLOAD)

        assert r.status_code == 201
        assert r.json() == {"received": True}

        lead = test_db.query(MarketingGuideLead).filter(MarketingGuideLead.email == "jane@acme.com").first()
        assert lead is not None
        assert lead.company == "Acme Corp"
        assert lead.guide_slug == "crm-sales-pipeline"
        assert lead.consented_at is not None
        mock_email.assert_called_once()

    def test_missing_consent_is_rejected(self, client, test_db: Session):
        payload = {**_VALID_PAYLOAD, "consented": False}
        r = client.post("/api/v1/marketing/guide-leads", json=payload)
        assert r.status_code == 422

        lead = test_db.query(MarketingGuideLead).filter(MarketingGuideLead.email == "jane@acme.com").first()
        assert lead is None

    def test_invalid_email_is_rejected(self, client, test_db: Session):
        payload = {**_VALID_PAYLOAD, "email": "not-an-email"}
        r = client.post("/api/v1/marketing/guide-leads", json=payload)
        assert r.status_code == 422

    def test_email_failure_does_not_fail_the_request(self, client, test_db: Session):
        """Matches app/api/invites.py's non-blocking email pattern - a
        notification failure shouldn't cost the visitor their download."""
        with patch("app.api.marketing_leads.send_marketing_guide_lead_email", side_effect=Exception("smtp down")):
            r = client.post("/api/v1/marketing/guide-leads", json=_VALID_PAYLOAD)

        assert r.status_code == 201
        lead = test_db.query(MarketingGuideLead).filter(MarketingGuideLead.email == "jane@acme.com").first()
        assert lead is not None
