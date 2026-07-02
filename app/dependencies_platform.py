"""Dependencies for platform (vendor staff) routes.

Fully separate boundary from app/dependencies.py: platform_access tokens are
signed with a distinct key and carry a distinct "type" claim, so they can
never be accepted by tenant get_current_user() and vice versa.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_platform_token
from app.models.platform_admin import PlatformAdmin
from app.schemas.platform import CurrentPlatformAdmin


def get_current_platform_admin(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> CurrentPlatformAdmin:
    """Extract and validate a platform JWT from request.

    🧨 CRITICAL: This is the ONLY boundary that grants cross-tenant access.
    Prefers Authorization header; falls back to the httpOnly
    bfp_platform_access cookie - mirrors tenant get_current_user().
    """
    header_token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        header_token = auth_header[7:]
    cookie_token = request.cookies.get("bfp_platform_access")

    candidate_tokens: list[str] = []
    if header_token:
        candidate_tokens.append(header_token)
    if cookie_token and cookie_token != header_token:
        candidate_tokens.append(cookie_token)

    if not candidate_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = None
    for candidate in candidate_tokens:
        try:
            payload = decode_platform_token(candidate)
            break
        except JWTError:
            continue
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "platform_access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin_id = payload.get("platform_admin_id")
    email = payload.get("email")
    if not admin_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    try:
        admin_uuid = UUID(str(admin_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims") from exc

    # Authoritative state comes from the DB, same idiom as tenant get_current_user.
    admin = (
        db.query(PlatformAdmin)
        .filter(
            PlatformAdmin.id == admin_uuid,
            PlatformAdmin.email == email,
            PlatformAdmin.is_active.is_(True),
        )
        .first()
    )
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_phash = payload.get("phash")
    if token_phash and token_phash != admin.hashed_password[-8:]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentPlatformAdmin(
        platform_admin_id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        platform_role=admin.platform_role,
        impersonation_allowed=admin.impersonation_allowed,
    )


def require_platform_role(*roles: str):
    """Dependency factory restricting access to specific platform_role values."""

    def _checker(
        current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    ) -> CurrentPlatformAdmin:
        if current_admin.platform_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return current_admin

    return _checker
