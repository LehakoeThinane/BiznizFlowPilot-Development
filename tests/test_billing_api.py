"""API-level tests for the public billing routes - checkout start and the
Stripe webhook receiver."""

from __future__ import annotations

from unittest.mock import patch

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization
from app.services.billing import BillingError


class TestStartCheckout:
    def test_returns_checkout_url(self, client, monkeypatch):
        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
        monkeypatch.setattr(settings, "stripe_price_ids", {"starter": "price_123"})

        with patch(
            "app.api.billing.create_checkout_session",
            return_value="https://checkout.stripe.com/pay/cs_test_xyz",
        ):
            response = client.post(
                "/api/v1/billing/checkout",
                json={"org_name": "Acme Corp", "owner_email": "owner@acme.com", "plan_tier": "starter"},
            )

        assert response.status_code == 200
        assert response.json() == {"checkout_url": "https://checkout.stripe.com/pay/cs_test_xyz"}

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


class TestStripeWebhook:
    def test_valid_checkout_completed_provisions_organization(self, client, test_db: Session):
        fake_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "customer": "cus_test_1",
                    "metadata": {
                        "org_name": "Webhook Co",
                        "subsidiary_name": "Webhook Co",
                        "primary_domain": "webhookco.com",
                        "owner_email": "owner@webhookco.com",
                        "plan_tier": "starter",
                    },
                }
            },
        }
        with (
            patch("app.api.billing.verify_webhook", return_value=fake_event),
            patch("app.services.billing.send_invite_email"),
        ):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=fake"},
            )

        assert response.status_code == 200
        assert response.json() == {"received": True}
        org = test_db.query(Organization).filter(Organization.stripe_customer_id == "cus_test_1").first()
        assert org is not None
        assert org.name == "Webhook Co"

    def test_invalid_signature_returns_400(self, client):
        with patch(
            "app.api.billing.verify_webhook",
            side_effect=stripe.error.SignatureVerificationError("bad", "sig"),
        ):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "bad"},
            )

        assert response.status_code == 400

    def test_unhandled_event_type_is_acknowledged_and_ignored(self, client, test_db: Session):
        fake_event = {"type": "customer.subscription.updated", "data": {"object": {}}}
        with patch("app.api.billing.verify_webhook", return_value=fake_event):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=fake"},
            )

        assert response.status_code == 200
        assert response.json() == {"received": True}

    def test_missing_metadata_returns_400(self, client, test_db: Session):
        fake_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_2", "customer": "cus_test_2", "metadata": {}}},
        }
        with patch("app.api.billing.verify_webhook", return_value=fake_event):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=fake"},
            )

        # Missing metadata raises BillingError inside handle_checkout_completed,
        # which the route maps to 400 (a bad/incomplete event), not 500.
        assert response.status_code == 400

    def test_unexpected_processing_error_returns_500(self, client, test_db: Session):
        """A genuine bug/transient failure (not a BillingError) maps to 500,
        so Stripe's normal retry schedule kicks in instead of giving up."""
        fake_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_3",
                    "customer": "cus_test_3",
                    "metadata": {
                        "org_name": "Boom Co",
                        "owner_email": "owner@boomco.com",
                    },
                }
            },
        }
        with (
            patch("app.api.billing.verify_webhook", return_value=fake_event),
            patch("app.api.billing.handle_checkout_completed", side_effect=RuntimeError("db exploded")),
        ):
            response = client.post(
                "/api/v1/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=fake"},
            )

        assert response.status_code == 500
