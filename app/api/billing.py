"""Billing API routes - public (no auth): starting a self-serve checkout and
receiving the Stripe webhook that completes it.

🧨 These routes are intentionally unauthenticated. /checkout is how a
brand-new, not-yet-existing customer starts a subscription - there is no
user to authenticate yet. /webhook is called by Stripe itself, authenticated
by signature verification (see BillingService.verify_webhook), not a JWT.
"""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.billing import CheckoutRequest, CheckoutResponse
from app.services.billing import BillingError, create_checkout_session, handle_checkout_completed, verify_webhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/checkout", response_model=CheckoutResponse)
@limiter.limit("10/minute")
def start_checkout(request: Request, body: CheckoutRequest) -> CheckoutResponse:
    """Start a self-serve subscription checkout for a brand-new client."""
    try:
        checkout_url = create_checkout_session(body)
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Receive and process Stripe webhook events.

    Only checkout.session.completed triggers provisioning; every other
    event type is acknowledged (200) and otherwise ignored, since this
    endpoint only needs to react to one thing regardless of which events
    the Stripe Dashboard is configured to send.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = verify_webhook(payload, sig_header)
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("billing.webhook.invalid_signature")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if event["type"] == "checkout.session.completed":
        try:
            handle_checkout_completed(db, event["data"]["object"])
        except BillingError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            db.rollback()
            logger.exception("billing.webhook.processing_error")
            # 500 (not 400): this is our failure, not a bad request - Stripe
            # should retry on its normal schedule in case it's transient.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process webhook"
            ) from exc

    return {"received": True}
