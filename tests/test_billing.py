"""Tests for BillingService - self-serve PayFast checkout and the ITN
handler that automatically provisions a new client Organization on payment
success.

PayFast network calls (DNS resolution and the server-confirmation POST) are
monkeypatched - no real PayFast account/keys or network access are needed to
run these; they exercise our own logic (field building, idempotency,
signature/IP/amount validation), not PayFast's infrastructure itself.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.payfast import build_signature
from app.models.organization import Organization
from app.models.pending_checkout import PendingCheckout
from app.schemas.billing import CheckoutRequest
from app.services.billing import BillingError, create_checkout_session, verify_and_process_itn


@pytest.fixture(autouse=True)
def _configured_payfast(monkeypatch):
    """Give every test a configured (fake) PayFast setup by default."""
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_merchant_key", "46f0cd694581a")
    monkeypatch.setattr(settings, "payfast_passphrase", "jt7NOE43FZPn")
    monkeypatch.setattr(settings, "payfast_sandbox", True)
    monkeypatch.setattr(settings, "payfast_plan_prices", {"starter": "8750.00", "professional": "35000.00"})


class TestBuildSignature:
    def test_matches_known_good_vector(self):
        """Golden test vector, hand-computed against PayFast's documented
        algorithm (ordered concat, quote_plus encoding, MD5) - locks in exact
        algorithm correctness independent of any live PayFast call."""
        fields = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "return_url": "https://app.example.com/checkout/success",
            "cancel_url": "https://app.example.com/checkout/cancelled",
            "notify_url": "https://api.example.com/api/v1/billing/payfast/notify",
            "name_first": "Acme Corp",
            "email_address": "owner@acme.com",
            "m_payment_id": "3fae1c2e-4b8e-4b6b-9c1a-1234567890ab",
            "amount": "8750.00",
            "item_name": "BiznizFlowPilot - Starter plan",
            "subscription_type": "1",
            "frequency": "3",
            "cycles": "0",
        }
        signature = build_signature(fields, "jt7NOE43FZPn")
        assert signature == "6d701547c0c03fc6f440a5991e930e8a"

    def test_blank_values_are_excluded(self):
        assert build_signature({"a": "1", "b": "", "c": "  "}, "pass") == build_signature({"a": "1"}, "pass")

    def test_field_order_changes_signature(self):
        assert build_signature({"a": "1", "b": "2"}, "pass") != build_signature({"b": "2", "a": "1"}, "pass")


class TestCreateCheckoutSession:
    def test_unconfigured_merchant_raises_billing_error(self, test_db: Session, monkeypatch):
        monkeypatch.setattr(settings, "payfast_merchant_id", "")
        with pytest.raises(BillingError, match="not configured"):
            create_checkout_session(
                test_db, CheckoutRequest(org_name="Acme", owner_email="a@acme.com", plan_tier="starter")
            )

    def test_unknown_plan_tier_raises_billing_error(self, test_db: Session):
        with pytest.raises(BillingError, match="Unknown plan tier"):
            create_checkout_session(
                test_db, CheckoutRequest(org_name="Acme", owner_email="a@acme.com", plan_tier="enterprise")
            )

    def test_creates_pending_checkout_and_signed_url(self, test_db: Session):
        url = create_checkout_session(
            test_db, CheckoutRequest(org_name="Acme Corp", owner_email="owner@acmecorp.com", plan_tier="starter")
        )

        assert url.startswith("https://sandbox.payfast.co.za/eng/process?")
        assert "amount=8750.00" in url
        assert "signature=" in url

        pending = test_db.query(PendingCheckout).filter(PendingCheckout.org_name == "Acme Corp").first()
        assert pending is not None
        assert pending.owner_email == "owner@acmecorp.com"
        assert pending.plan_tier == "starter"
        assert pending.status == "pending"
        assert f"m_payment_id={pending.id}" in url


class TestVerifyAndProcessItn:
    def _pending(self, test_db: Session, **overrides) -> PendingCheckout:
        pending = PendingCheckout(
            org_name="Acme Corp",
            subsidiary_name="Acme Corp",
            owner_email="owner@acmecorp.com",
            plan_tier="starter",
            **overrides,
        )
        test_db.add(pending)
        test_db.commit()
        test_db.refresh(pending)
        return pending

    def _signed_fields(self, pending_id, **overrides) -> dict[str, str]:
        fields = {
            "m_payment_id": str(pending_id),
            "amount_gross": "8750.00",
            "token": "tok_abc123",
        }
        fields.update(overrides)
        fields["signature"] = build_signature(fields, settings.payfast_passphrase)
        return fields

    def test_provisions_organization_and_sends_invite(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id)

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
            patch("app.services.billing.send_invite_email") as mock_send,
        ):
            verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

        org = test_db.query(Organization).filter(Organization.payfast_token == "tok_abc123").first()
        assert org is not None
        assert org.name == "Acme Corp"
        assert org.subscription_status == "active"
        assert org.plan_tier == "starter"
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == "owner@acmecorp.com"

        test_db.refresh(pending)
        assert pending.status == "completed"

    def test_duplicate_itn_delivery_is_a_no_op(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id)

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
            patch("app.services.billing.send_invite_email"),
        ):
            verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

            with patch("app.services.billing.send_invite_email") as mock_send_second:
                verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

        mock_send_second.assert_not_called()
        count = test_db.query(Organization).filter(Organization.payfast_token == "tok_abc123").count()
        assert count == 1

    def test_bad_signature_is_rejected(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id)
        fields["amount_gross"] = "1.00"  # tampered after signing

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
        ):
            with pytest.raises(BillingError, match="Signature mismatch"):
                verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

    def test_untrusted_ip_is_rejected(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id)

        with patch("app.services.billing.validate_source_ip", return_value=False):
            with pytest.raises(BillingError, match="Untrusted source IP"):
                verify_and_process_itn(test_db, b"raw", fields, "1.2.3.4")

    def test_server_confirmation_failure_is_rejected(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id)

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=False),
        ):
            with pytest.raises(BillingError, match="server confirmation failed"):
                verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

    def test_amount_mismatch_is_rejected(self, test_db: Session):
        pending = self._pending(test_db)
        fields = self._signed_fields(pending.id, amount_gross="1.00")

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
        ):
            with pytest.raises(BillingError, match="Amount mismatch"):
                verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")

    def test_missing_pending_checkout_is_rejected(self, test_db: Session):
        import uuid

        fields = self._signed_fields(uuid.uuid4())

        with (
            patch("app.services.billing.validate_source_ip", return_value=True),
            patch("app.services.billing.confirm_with_payfast", return_value=True),
        ):
            with pytest.raises(BillingError, match="No matching pending checkout"):
                verify_and_process_itn(test_db, b"raw", fields, "197.97.145.144")
