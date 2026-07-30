"""Public free-trial signup routes.

Deliberately separate from app/api/auth.py's invite-based onboarding - this
is the demo/trial entry point for portfolio visitors, not a replacement for
how real paying customers get onboarded. Unauthenticated by design, so it is
registered in app/main.py outside any require_active_trial-gated block.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.auth import _set_access_cookie, _set_refresh_cookie, _set_session_cookie
from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import TokenResponse
from app.schemas.signup import TrialSignupGoogleRequest, TrialSignupRequest
from app.services.trial_signup import TrialSignupService

router = APIRouter(prefix="/signup", tags=["signup"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)


@router.post("/trial", response_model=TokenResponse)
@limiter.limit("5/hour")
def signup_trial(
    request: Request,
    body: TrialSignupRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Start a free trial with email/password. Creates a brand-new private
    trial business, seeds it with sample data, and logs the new owner in."""
    service = TrialSignupService(db)
    try:
        tokens = service.create_via_password(
            organization_name=body.organization_name,
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    _set_refresh_cookie(response, tokens.refresh_token)
    _set_access_cookie(response, tokens.access_token)
    _set_session_cookie(response)
    return tokens


@router.post("/trial/google", response_model=TokenResponse)
@limiter.limit("20/minute")
def signup_trial_google(
    request: Request,
    body: TrialSignupGoogleRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Start a free trial via Google Sign-In, or log back in if this Google
    account already has a business from an earlier signup - including a real,
    fully onboarded customer, not just other trials (see create_via_google's
    existing-user lookup, which isn't restricted to trial-tier accounts).

    🧨 Deliberately much more generous than /trial's 5/hour: this same route
    also backs the LOGIN page's "Continue with Google" button (any returning
    user, any plan tier - see frontend's signupTrialWithGoogle call from
    login/page.tsx), not just new trial creation. A per-IP quota tight enough
    to bound spam trial-account creation was locking out every real user
    behind a shared office/carrier IP once anyone nearby had signed in a
    handful of times. The anti-abuse backstop for trial creation is really
    the Google-verified ID token itself (can't be minted cheaply at volume),
    not this quota.
    """
    service = TrialSignupService(db)
    try:
        tokens = service.create_via_google(
            organization_name=body.organization_name,
            credential=body.credential,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    _set_refresh_cookie(response, tokens.refresh_token)
    _set_access_cookie(response, tokens.access_token)
    _set_session_cookie(response)
    return tokens
