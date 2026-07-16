"""API-level tests for the public billing routes - checkout start and the
PayFast ITN receiver."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.payfast import build_signature
from app.models.organization import Organization
from app.models.pending_checkout import PendingCheckout
from app.services.billing import BillingError


@pytest.fixture(autouse=True)
def _configured_payfast(monkeypatch):
    monkeypatch.setattr(settings, "payfast_passphrase", "jt7NOE43FZPn")


class TestStartCheckout:
    def test_returns_checkout_url(self, client):
        with patch(
            "app.api.billing.create_checkout_session",
            return_value="https://sandbox.payfast.co.za/eng/process?merchant_id=10000100",
        ):
            response = client.post(
                "/api/v1/billing/checkout",
                json={"org_name": "Acme Corp", "owner_email": "owner@acme.com", "plan_tier": "starter"},
            )

        assert response.status_code == 200
        assert response.json() == {"checkout_url": "https://sandbox.payfast.co.za/eng/process?merchant_id=10000100"}

    def test_billing_error_returns_400(self, client):
        with patch(
            "app.api.billing.create_checkout_session",
            side_effect=BillingError("nope"),
        ):
            response = client.post(
                "/api/v1/billing/checkout",
                json={"org_name": "Acme Corp", "owner_email": "owner@acme.com", "plan_tier": "starter"},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "nope"

    def test_invalid_plan_tier_is_rejected_by_schema(self, client):
        response = client.post(
            "/api/v1/billing/checkout",
            json={"org_name": "Acme Corp", "owner_email": "owner@acme.com", "plan_tier": "not-a-real-tier"},
        )
        assert response.status_code == 422


class TestPayfastItn:
    def _pending(self, test_db: Session) -> PendingCheckout:
        pending = PendingCheckout(
            org_name="Webhook Co",
            subsidiary_name="Webhook Co",
            owner_email="owner@webhookco.com",
            plan_tier="starter",
        )
        test_db.add(pending)
        test_db.commit()
        test_db.refresh(pending)
        return pending

    def test_valid_itn_provisions_organization(self, client, test_db: Session):
        pending = self._pending(test_db)
        fields = {"m_payment_id": str(pending.id), "amount_gross": "8750.00", "token": "tok_1"}
        fields["signature"] = build_signature(fields, settings.payfast_passphrase)

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
            patch("app.services.billing.send_invite_email"),
        ):
            response = client.post("/api/v1/billing/payfast/notify", data=fields)

        assert response.status_code == 200
        assert response.json() == {"received": True}
        org = test_db.query(Organization).filter(Organization.payfast_token == "tok_1").first()
        assert org is not None
        assert org.name == "Webhook Co"

    def test_rejected_itn_is_still_acknowledged_with_200(self, client, test_db: Session):
        """A failed validation is logged and dropped, not surfaced as an
        error - PayFast shouldn't retry-storm a spoofed/malformed ITN."""
        with patch("app.services.billing.validate_source_ip", return_value=False):
            response = client.post(
                "/api/v1/billing/payfast/notify",
                data={"m_payment_id": "does-not-matter", "signature": "x"},
            )

        assert response.status_code == 200
        assert response.json() == {"received": True}

    def test_unexpected_processing_error_returns_500(self, client, test_db: Session):
        """A genuine bug/transient failure (not a BillingError) maps to 500,
        so PayFast's normal retry schedule kicks in instead of giving up."""
        with patch(
            "app.api.billing.verify_and_process_itn",
            side_effect=RuntimeError("db exploded"),
        ):
            response = client.post(
                "/api/v1/billing/payfast/notify",
                data={"m_payment_id": "does-not-matter", "signature": "x"},
            )

        assert response.status_code == 500
