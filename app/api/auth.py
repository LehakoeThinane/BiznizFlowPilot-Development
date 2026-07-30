"""Authentication API routes."""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    TokenResponse,
)
from app.schemas.invitation import InvitationAcceptRequest, InvitationValidateResponse
from app.services.auth import AuthService
from app.services.email import send_password_reset_email
from app.services.invitation import InvitationService

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)

_COOKIE_SECURE = settings.environment == "production"
_COOKIE_SAMESITE = "strict" if _COOKIE_SECURE else "lax"
_REFRESH_COOKIE = "bfp_refresh"
_ACCESS_COOKIE = "bfp_access"
# Non-httpOnly session indicator — lets JS know the user is authenticated
# without exposing the actual JWT. Value is "1"; contains no sensitive data.
_SESSION_COOKIE = "bfp_session"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.refresh_token_expiration_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def _set_access_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.jwt_expiration_hours * 60 * 60,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE, path="/api/v1/auth")


def _set_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=_SESSION_COOKIE,
        value="1",
        httponly=False,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.jwt_expiration_hours * 60 * 60,
        path="/",
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key=_ACCESS_COOKIE, path="/")


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_SESSION_COOKIE, path="/")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login with email and password. Returns JWT access and refresh tokens."""
    service = AuthService(db)
    try:
        tokens = service.login(email=body.email, password=body.password)
        _set_refresh_cookie(response, tokens.refresh_token)
        _set_access_cookie(response, tokens.access_token)
        _set_session_cookie(response)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_payload: str | dict[str, str] | None = Body(default=None),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    Reads the refresh token from the httpOnly cookie first; falls back to the
    request body for clients that cannot use cookies.
    """
    # Cookie takes priority (more secure); fall back to explicit body
    refresh_token_body: str | None = None
    if isinstance(refresh_payload, str):
        refresh_token_body = refresh_payload
    elif isinstance(refresh_payload, dict):
        refresh_token_body = refresh_payload.get("refresh_token")

    token_value = request.cookies.get(_REFRESH_COOKIE) or refresh_token_body
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    service = AuthService(db)
    try:
        tokens = service.refresh_tokens(token_value)
        _set_refresh_cookie(response, tokens.refresh_token)
        _set_access_cookie(response, tokens.access_token)
        _set_session_cookie(response)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    """Clear the httpOnly refresh and access token cookies and session indicator."""
    _clear_refresh_cookie(response)
    _clear_access_cookie(response)
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out successfully")


@router.post("/password-reset/request", response_model=MessageResponse)
@limiter.limit("5/minute")
def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Send a password reset link to the user's email address.

    Always returns the same generic message to prevent user enumeration.
    """
    service = AuthService(db)
    try:
        reset_token = service.request_password_reset(email=body.email)
        try:
            send_password_reset_email(to_email=body.email, reset_token=reset_token)
        except Exception:
            # Email delivery failure is logged inside send_password_reset_email;
            # we still return success to avoid leaking whether the address exists.
            pass
    except ValueError:
        pass  # Unknown email — return generic message to prevent enumeration
    return MessageResponse(message="If this email is registered, a reset link has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
@limiter.limit("5/minute")
def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Reset user password using a valid password reset token."""
    service = AuthService(db)
    try:
        service.reset_password(token=body.token, new_password=body.new_password)
        return MessageResponse(message="Password reset successful")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/invite/validate", response_model=InvitationValidateResponse)
@limiter.limit("10/minute")
def validate_invite(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> InvitationValidateResponse:
    """Lightweight pre-check for the accept-invite page. No auth required."""
    service = InvitationService(db)
    try:
        invitation = service.validate_token(token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    org_name, business_name = service.get_display_context(invitation)
    local, _, domain = invitation.email.partition("@")
    masked = f"{local[:2]}***@{domain}" if len(local) > 2 else f"***@{domain}"

    return InvitationValidateResponse(
        organization_name=org_name,
        business_name=business_name,
        masked_email=masked,
        role=invitation.role,
    )


@router.post("/invite/accept", response_model=TokenResponse)
@limiter.limit("5/minute")
def accept_invite(
    request: Request,
    body: InvitationAcceptRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Accept an invitation, creating the account and logging in."""
    service = InvitationService(db)
    try:
        tokens = service.accept_invitation(
            raw_token=body.token,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
        )
        _set_refresh_cookie(response, tokens.refresh_token)
        _set_access_cookie(response, tokens.access_token)
        _set_session_cookie(response)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
