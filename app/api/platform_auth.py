"""Platform authentication API routes - vendor staff login, separate cookie jar."""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.auth import MessageResponse
from app.schemas.platform import PlatformLoginRequest, PlatformTokenResponse
from app.services.platform_auth import PlatformAuthService

router = APIRouter(prefix="/platform/v1/auth", tags=["platform-auth"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)

_COOKIE_SECURE = settings.environment == "production"
_COOKIE_SAMESITE = "strict" if _COOKIE_SECURE else "lax"
_REFRESH_COOKIE = "bfp_platform_refresh"
_ACCESS_COOKIE = "bfp_platform_access"


def _set_platform_cookies(response: Response, tokens: PlatformTokenResponse) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=tokens.access_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.platform_jwt_expiration_hours * 60 * 60,
        path="/",
    )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=tokens.refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        max_age=settings.platform_refresh_token_expiration_days * 24 * 60 * 60,
        path="/platform/v1/auth",
    )


def _clear_platform_cookies(response: Response) -> None:
    response.delete_cookie(key=_ACCESS_COOKIE, path="/")
    response.delete_cookie(key=_REFRESH_COOKIE, path="/platform/v1/auth")


@router.post("/login", response_model=PlatformTokenResponse)
@limiter.limit("10/minute")
def platform_login(
    request: Request,
    body: PlatformLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> PlatformTokenResponse:
    """Login a platform (vendor staff) admin. No self-registration - admins are
    bootstrapped via scripts/create_platform_admin.py or POST /platform/v1/admins."""
    service = PlatformAuthService(db)
    try:
        tokens = service.login(email=body.email, password=body.password)
        _set_platform_cookies(response, tokens)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/refresh", response_model=PlatformTokenResponse)
@limiter.limit("30/minute")
def platform_refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_payload: str | dict[str, str] | None = Body(default=None),
) -> PlatformTokenResponse:
    """Exchange a valid platform refresh token for a new access + refresh pair."""
    refresh_token_body: str | None = None
    if isinstance(refresh_payload, str):
        refresh_token_body = refresh_payload
    elif isinstance(refresh_payload, dict):
        refresh_token_body = refresh_payload.get("refresh_token")

    token_value = request.cookies.get(_REFRESH_COOKIE) or refresh_token_body
    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")

    service = PlatformAuthService(db)
    try:
        tokens = service.refresh_tokens(token_value)
        _set_platform_cookies(response, tokens)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e


@router.post("/logout", response_model=MessageResponse)
def platform_logout(response: Response) -> MessageResponse:
    """Clear the platform httpOnly cookies."""
    _clear_platform_cookies(response)
    return MessageResponse(message="Logged out successfully")
