"""Billing service - Stripe checkout for self-serve signup, and the webhook
handler that automatically provisions a new client Organization once payment
succeeds.

No owner password is collected at checkout - the owner sets their own
credentials by accepting the same invite-token email used everywhere else in
this codebase (see app/services/invitation.py), so BiznizFlowPilot never sees
or sets a client's password, self-serve or not.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization
from app.schemas.billing import CheckoutRequest
from app.services.email import send_invite_email
from app.services.invitation import InvitationService
from app.services.organization import OrganizationService

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Raised for a billing operation the caller should surface as an HTTP error."""


def create_checkout_session(data: CheckoutRequest) -> str:
    """Create a Stripe Checkout Session for a new subscription and return its URL.

    Company/owner details travel through as Checkout metadata, since the
    webhook handler only receives the Stripe event - not this request - when
    payment completes. primary_domain is derived from owner_email rather than
    collected separately, so the owner's own eventual invite is guaranteed to
    match the domain restriction it's checked against (see
    InvitationService.create_invitation / domain_is_authorized).
    """
    if not settings.stripe_secret_key:
        raise BillingError("Billing is not configured")

    price_id = settings.stripe_price_ids.get(data.plan_tier)
    if not price_id:
        raise BillingError(f"Unknown plan tier: {data.plan_tier!r}")

    primary_domain = data.owner_email.rsplit("@", 1)[-1].lower()

    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=data.owner_email,
            success_url=f"{settings.frontend_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/checkout/cancelled",
            metadata={
                "org_name": data.org_name,
                "subsidiary_name": data.subsidiary_name or data.org_name,
                "primary_domain": primary_domain,
                "owner_email": data.owner_email,
                "plan_tier": data.plan_tier,
            },
        )
    except stripe.error.StripeError as exc:
        logger.exception("billing.checkout.stripe_error")
        raise BillingError(f"Could not start checkout: {exc}") from exc

    if not session.url:
        raise BillingError("Stripe did not return a checkout URL")
    return session.url


def verify_webhook(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify a Stripe webhook signature and return the parsed Event.

    Raises stripe.error.SignatureVerificationError on an invalid/forged
    signature - callers must map that to a 400, not a 500.
    """
    if not settings.stripe_webhook_secret:
        raise BillingError("Webhook secret is not configured")
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)


def handle_checkout_completed(db: Session, session_data: dict[str, Any]) -> None:
    """Provision the Organization for a completed self-serve checkout.

    Idempotent: Stripe delivers webhooks at-least-once, so if an
    Organization already exists for this Stripe customer (a redelivered
    event), this is a no-op rather than a duplicate provision.
    """
    stripe_customer_id = session_data.get("customer")
    metadata = session_data.get("metadata") or {}
    org_name = metadata.get("org_name")
    owner_email = metadata.get("owner_email")

    if not stripe_customer_id or not org_name or not owner_email:
        logger.error(
            "billing.webhook.missing_metadata",
            extra={"session_id": session_data.get("id")},
        )
        raise BillingError("Checkout session is missing required metadata")

    existing = (
        db.query(Organization)
        .filter(Organization.stripe_customer_id == stripe_customer_id)
        .first()
    )
    if existing is not None:
        logger.info(
            "billing.webhook.duplicate_delivery",
            extra={"stripe_customer_id": stripe_customer_id, "organization_id": str(existing.id)},
        )
        return

    org_service = OrganizationService(db)
    shell = org_service.create_organization_shell(
        org_name=org_name,
        billing_email=owner_email,
        subsidiary_name=metadata.get("subsidiary_name") or org_name,
        primary_domain=metadata.get("primary_domain"),
        plan_tier=metadata.get("plan_tier") or "starter",
    )
    shell.organization.stripe_customer_id = stripe_customer_id
    shell.organization.subscription_status = "active"
    db.flush()

    invitation, raw_token = InvitationService(db).create_invitation(
        business_id=shell.business.id,
        organization_id=shell.organization.id,
        email=owner_email,
        role="owner",
        invited_by=None,
        inviter_role="system",
        inviter_name="BiznizFlowPilot",
    )

    try:
        send_invite_email(
            to_email=owner_email,
            organization_name=shell.organization.name,
            business_name=shell.business.name,
            invited_by_name="BiznizFlowPilot",
            raw_token=raw_token,
        )
    except Exception:
        pass  # email delivery failure is logged inside send_invite_email

    db.commit()
    logger.info(
        "billing.webhook.provisioned",
        extra={
            "organization_id": str(shell.organization.id),
            "business_id": str(shell.business.id),
            "invitation_id": str(invitation.id),
            "stripe_customer_id": stripe_customer_id,
        },
    )
