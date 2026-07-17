"""Billing API routes - public (no auth): starting a self-serve checkout and
receiving the PayFast ITN that completes it.

🧨 These routes are intentionally unauthenticated. /checkout is how a
brand-new, not-yet-existing customer starts a subscription - there is no
user to authenticate yet. /payfast/notify is called by PayFast itself,
authenticated by signature + source-IP + server-confirmation checks (see
BillingService.verify_and_process_itn), not a JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.billing import CheckoutRequest, CheckoutResponse
from app.services.billing import BillingError, create_checkout_session, verify_and_process_itn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/checkout", response_model=CheckoutResponse)
@limiter.limit("10/minute")
def start_checkout(request: Request, body: CheckoutRequest, db: Session = Depends(get_db)) -> CheckoutResponse:
    """Start a self-serve subscription checkout for a brand-new client."""
    try:
        checkout_url = create_checkout_session(db, body)
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/payfast/notify", status_code=status.HTTP_200_OK)
async def payfast_itn(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Receive and process a PayFast ITN (Instant Transaction Notification).

    Validation failures (bad signature, untrusted source IP, amount
    mismatch, ...) are logged and acknowledged with 200 rather than raising -
    a failure here almost always means a spoofed or malformed request, not a
    transient one, so there's nothing for PayFast to usefully retry. Genuine
    server errors map to 500 so PayFast's normal retry schedule kicks in.
    """
    raw_body = await request.body()
    form = await request.form()
    fields = {key: str(value) for key, value in form.items()}
    client_ip = get_remote_address(request)

    try:
        verify_and_process_itn(db, raw_body, fields, client_ip)
    except BillingError as exc:
        db.rollback()
        logger.warning("billing.itn.rejected", extra={"reason": str(exc), "client_ip": client_ip})
    except Exception as exc:
        db.rollback()
        logger.exception("billing.itn.processing_error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process ITN") from exc

    return {"received": True}
