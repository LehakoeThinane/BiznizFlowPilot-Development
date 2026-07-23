"""Billing schemas - self-serve checkout for new client signups."""

from pydantic import BaseModel, EmailStr, Field


class CheckoutRequest(BaseModel):
    """Start a self-serve subscription checkout for a brand-new client.

    No password is collected here - the owner sets their own credentials by
    accepting the invite email sent automatically once payment succeeds
    (see app/services/billing.py::handle_checkout_completed).

    owner_email and business_email are deliberately separate: owner_email is
    only the billing/payment contact sent to PayFast and may be a personal
    address; business_email is the custom-domain address that actually
    receives the platform registration invite and becomes the org's
    authorized domain - personal/free email providers are rejected there.
    """

    org_name: str = Field(..., min_length=1, max_length=255)
    subsidiary_name: str | None = None
    owner_email: EmailStr
    business_email: EmailStr
    plan_tier: str = Field(..., pattern=r"^(starter|growth|professional|enterprise)$")


class CheckoutResponse(BaseModel):
    """Where to send the browser to complete payment."""

    checkout_url: str
