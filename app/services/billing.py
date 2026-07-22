"""Billing service - PayFast checkout for self-serve signup, and the ITN
(Instant Transaction Notification) handler that automatically provisions a
new client Organization once payment succeeds.

No owner password is collected at checkout - the owner sets their own
credentials by accepting the same invite-token email used everywhere else in
this codebase (see app/services/invitation.py), so BiznizFlowPilot never sees
or sets a client's password, self-serve or not.

PayFast has no server-side "session" object like Stripe's Checkout Session -
checkout is a signed redirect to their hosted payment page, and the only way
to carry our own context (org name, email, plan) across that redirect is a
PendingCheckout row, looked back up by id when the ITN arrives.
"""

from __future__ import annotations

import logging
import uuid
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.payfast import build_signature, confirm_with_payfast, payfast_host, validate_source_ip
from app.repositories.pending_checkout import PendingCheckoutRepository
from app.schemas.billing import CheckoutRequest
from app.services.email import send_invite_email
from app.services.invitation import InvitationService
from app.services.organization import OrganizationService

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Raised for a billing operation the caller should surface as an HTTP error."""


# business_email (the platform-registration address, distinct from
# owner_email's billing/payment role) must be a custom business domain -
# personal/free webmail providers are rejected. Free trial signup
# (app/services/trial_signup.py) deliberately accepts any domain including
# these; this blocklist applies only to paid checkout's business_email.
_BLOCKED_EMAIL_DOMAINS = {
    # Global consumer webmail
    "gmail.com", "googlemail.com",
    "yahoo.com", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "protonmail.com", "proton.me",
    "gmx.com", "gmx.net", "mail.com",
    "yandex.com", "zoho.com",
    # South African / regional consumer webmail
    "yahoo.co.za", "webmail.co.za", "mweb.co.za", "telkomsa.net",
    "vodamail.co.za", "lantic.net",
}


def _is_free_email_domain(email: str) -> bool:
    return email.rsplit("@", 1)[-1].strip().lower() in _BLOCKED_EMAIL_DOMAINS


def create_checkout_session(db: Session, data: CheckoutRequest) -> str:
    """Create a PendingCheckout row and return a signed PayFast redirect URL.

    business_email (not owner_email) is what the owner's eventual invite
    goes to and what primary_domain is derived from at ITN time - see
    verify_and_process_itn.
    """
    if not (settings.payfast_merchant_id and settings.payfast_merchant_key):
        raise BillingError("Billing is not configured")

    amount = settings.payfast_plan_prices.get(data.plan_tier)
    if not amount:
        raise BillingError(f"Unknown plan tier: {data.plan_tier!r}")

    if _is_free_email_domain(data.business_email):
        raise BillingError(
            "Please use your business email address to register - "
            "personal email providers like Gmail, Yahoo, or Outlook aren't accepted."
        )

    pending = PendingCheckoutRepository(db).create(
        org_name=data.org_name,
        subsidiary_name=data.subsidiary_name or data.org_name,
        owner_email=data.owner_email,
        business_email=data.business_email,
        plan_tier=data.plan_tier,
    )

    fields = {
        "merchant_id": settings.payfast_merchant_id,
        "merchant_key": settings.payfast_merchant_key,
        "return_url": f"{settings.frontend_url}/checkout/success",
        "cancel_url": f"{settings.frontend_url}/checkout/cancelled",
        "notify_url": f"{settings.api_base_url}/api/v1/billing/payfast/notify",
        "name_first": data.org_name,
        "email_address": data.owner_email,
        "m_payment_id": str(pending.id),
        "amount": amount,
        "item_name": f"BiznizFlowPilot - {data.plan_tier.title()} plan",
        "subscription_type": "1",
        "frequency": "3",  # monthly
        "cycles": "0",  # indefinite, until cancelled
    }
    fields["signature"] = build_signature(fields, settings.payfast_passphrase)
    return f"https://{payfast_host()}/eng/process?{urlencode(fields)}"


def verify_and_process_itn(db: Session, raw_body: bytes, fields: dict[str, str], client_ip: str) -> None:
    """Validate an incoming PayFast ITN and, if genuine and new, provision the
    Organization it paid for.

    Four checks, in PayFast's documented order - a failure at any step raises
    BillingError, which the caller (app/api/billing.py) logs and acknowledges
    with 200 rather than retrying, since a failed check here almost always
    means a spoofed or malformed request rather than a transient failure.
    """
    received_signature = fields.get("signature", "")
    signable_fields = {k: v for k, v in fields.items() if k != "signature"}
    if build_signature(signable_fields, settings.payfast_passphrase) != received_signature:
        raise BillingError("Signature mismatch")

    if not validate_source_ip(client_ip):
        raise BillingError(f"Untrusted source IP: {client_ip}")

    if not confirm_with_payfast(raw_body):
        raise BillingError("PayFast server confirmation failed")

    try:
        m_payment_id = uuid.UUID(fields.get("m_payment_id", ""))
    except ValueError as exc:
        raise BillingError("Invalid m_payment_id") from exc
    pending = PendingCheckoutRepository(db).get(m_payment_id)
    if pending is None:
        raise BillingError("No matching pending checkout")

    expected_amount = settings.payfast_plan_prices.get(pending.plan_tier)
    try:
        amounts_match = expected_amount is not None and abs(float(fields.get("amount_gross", 0)) - float(expected_amount)) < 0.01
    except ValueError:
        amounts_match = False
    if not amounts_match:
        raise BillingError("Amount mismatch")

    if pending.status == "completed":
        logger.info("billing.itn.duplicate_delivery", extra={"pending_checkout_id": str(pending.id)})
        return

    org_service = OrganizationService(db)
    primary_domain = pending.business_email.rsplit("@", 1)[-1].lower()
    shell = org_service.create_organization_shell(
        org_name=pending.org_name,
        billing_email=pending.owner_email,
        subsidiary_name=pending.subsidiary_name or pending.org_name,
        primary_domain=primary_domain,
        plan_tier=pending.plan_tier,
    )
    shell.organization.payfast_token = fields.get("token")
    shell.organization.subscription_status = "active"
    pending.status = "completed"
    db.flush()

    invitation, raw_token = InvitationService(db).create_invitation(
        business_id=shell.business.id,
        organization_id=shell.organization.id,
        email=pending.business_email,
        role="owner",
        invited_by=None,
        inviter_role="system",
        inviter_name="BiznizFlowPilot",
    )

    try:
        send_invite_email(
            to_email=pending.business_email,
            organization_name=shell.organization.name,
            business_name=shell.business.name,
            invited_by_name="BiznizFlowPilot",
            raw_token=raw_token,
        )
    except Exception:
        pass  # email delivery failure is logged inside send_invite_email

    db.commit()
    logger.info(
        "billing.itn.provisioned",
        extra={
            "organization_id": str(shell.organization.id),
            "business_id": str(shell.business.id),
            "invitation_id": str(invitation.id),
            "pending_checkout_id": str(pending.id),
        },
    )
