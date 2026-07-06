"""Billing schemas - self-serve checkout for new client signups."""

from pydantic import BaseModel, EmailStr, Field


class CheckoutRequest(BaseModel):
    """Start a self-serve subscription checkout for a brand-new client.

    No password is collected here - the owner sets their own credentials by
    accepting the invite email sent automatically once payment succeeds
    (see app/services/billing.py::handle_checkout_completed).
    """

    org_name: str = Field(..., min_length=1, max_length=255)
    subsidiary_name: str | None = None
    owner_email: EmailStr
    plan_tier: str = Field(..., pattern=r"^(starter|professional|enterprise)$")


class CheckoutResponse(BaseModel):
    """Where to send the browser to complete payment."""

    checkout_url: str
