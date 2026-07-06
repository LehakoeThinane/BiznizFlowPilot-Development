"""Tests for BillingService - self-serve Stripe checkout and the webhook
that automatically provisions a new client Organization on payment success.

All Stripe SDK calls are mocked - no real Stripe account/keys are needed to
run these; they exercise our own logic (metadata construction, idempotency,
signature-error mapping), not Stripe's API itself.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization
from app.schemas.billing import CheckoutRequest
from app.services.billing import (
    BillingError,
    create_checkout_session,
    handle_checkout_completed,
    verify_webhook,
)


@pytest.fixture(autouse=True)
def _configured_stripe(monkeypatch):
    """Give every test a configured (fake) Stripe setup by default."""
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    monkeypatch.setattr(settings, "stripe_price_ids", {"starter": "price_starter_123"})


class TestCreateCheckoutSession:
    def test_creates_session_with_derived_domain_and_metadata(self):
        fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_123")
        with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
            url = create_checkout_session(
                CheckoutRequest(
                    org_name="Acme Corp",
                    owner_email="owner@acmecorp.com",
                    plan_tier="starter",
                )
            )

        assert url == "https://checkout.stripe.com/pay/cs_test_123"
        kwargs = mock_create.call_args.kwargs
        assert kwargs["mode"] == "subscription"
        assert kwargs["line_items"] == [{"price": "price_starter_123", "quantity": 1}]
        assert kwargs["customer_email"] == "owner@acmecorp.com"
        assert kwargs["metadata"]["org_name"] == "Acme Corp"
        assert kwargs["metadata"]["owner_email"] == "owner@acmecorp.com"
        # Derived from owner_email, not separately collected - guarantees the
        # owner's own later invite always matches this domain.
        assert kwargs["metadata"]["primary_domain"] == "acmecorp.com"
        assert kwargs["metadata"]["plan_tier"] == "starter"

    def test_unconfigured_stripe_raises_billing_error(self, monkeypatch):
        monkeypatch.setattr(settings, "stripe_secret_key", "")
        with pytest.raises(BillingError, match="not configured"):
            create_checkout_session(
                CheckoutRequest(org_name="Acme", owner_email="a@acme.com", plan_tier="starter")
            )

    def test_unknown_plan_tier_raises_billing_error(self):
        with pytest.raises(BillingError, match="Unknown plan tier"):
            create_checkout_session(
                CheckoutRequest(org_name="Acme", owner_email="a@acme.com", plan_tier="enterprise")
            )

    def test_stripe_api_error_is_wrapped(self):
        with patch(
            "stripe.checkout.Session.create",
            side_effect=stripe.error.StripeError("card declined or whatever"),
        ):
            with pytest.raises(BillingError, match="Could not start checkout"):
                create_checkout_session(
                    CheckoutRequest(org_name="Acme", owner_email="a@acme.com", plan_tier="starter")
                )


class TestVerifyWebhook:
    def test_delegates_to_stripe_sdk(self):
        fake_event = {"type": "checkout.session.completed"}
        with patch("stripe.Webhook.construct_event", return_value=fake_event) as mock_construct:
            result = verify_webhook(b'{"payload": true}', "t=123,v1=abc")

        assert result == fake_event
        mock_construct.assert_called_once_with(b'{"payload": true}', "t=123,v1=abc", "whsec_fake")

    def test_unconfigured_secret_raises_billing_error(self, monkeypatch):
        monkeypatch.setattr(settings, "stripe_webhook_secret", "")
        with pytest.raises(BillingError, match="not configured"):
            verify_webhook(b"{}", "sig")

    def test_invalid_signature_propagates(self):
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad sig", "sig_header"),
        ):
            with pytest.raises(stripe.error.SignatureVerificationError):
                verify_webhook(b"{}", "bad-sig")


class TestHandleCheckoutCompleted:
    def _session_data(self, **overrides) -> dict:
        data = {
            "id": "cs_test_123",
            "customer": "cus_test_abc",
            "metadata": {
                "org_name": "Acme Corp",
                "subsidiary_name": "Acme Corp",
                "primary_domain": "acmecorp.com",
                "owner_email": "owner@acmecorp.com",
                "plan_tier": "starter",
            },
        }
        data.update(overrides)
        return data

    def test_provisions_organization_and_sends_invite(self, test_db: Session):
        with patch("app.services.billing.send_invite_email") as mock_send:
            handle_checkout_completed(test_db, self._session_data())

        org = test_db.query(Organization).filter(Organization.stripe_customer_id == "cus_test_abc").first()
        assert org is not None
        assert org.name == "Acme Corp"
        assert org.subscription_status == "active"
        assert org.plan_tier == "starter"
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == "owner@acmecorp.com"

    def test_duplicate_webhook_delivery_is_a_no_op(self, test_db: Session):
        with patch("app.services.billing.send_invite_email"):
            handle_checkout_completed(test_db, self._session_data())

            with patch("app.services.billing.send_invite_email") as mock_send_second:
                handle_checkout_completed(test_db, self._session_data())

        # Second delivery for the same Stripe customer must not create a
        # second organization or send a second invite.
        mock_send_second.assert_not_called()
        count = (
            test_db.query(Organization)
            .filter(Organization.stripe_customer_id == "cus_test_abc")
            .count()
        )
        assert count == 1

    def test_missing_metadata_raises_billing_error(self, test_db: Session):
        with pytest.raises(BillingError, match="missing required metadata"):
            handle_checkout_completed(test_db, self._session_data(metadata={}))

    def test_owner_invite_matches_derived_domain(self, test_db: Session):
        """The domain check inside create_invitation must pass for the
        owner's own invite - this is exactly why primary_domain is derived
        from owner_email rather than trusted as a separate field."""
        with patch("app.services.billing.send_invite_email"):
            handle_checkout_completed(test_db, self._session_data())

        from app.models.user_invitation import UserInvitation

        invite = (
            test_db.query(UserInvitation)
            .filter(UserInvitation.email == "owner@acmecorp.com")
            .first()
        )
        assert invite is not None
        assert invite.role == "owner"
        assert invite.status == "pending"
