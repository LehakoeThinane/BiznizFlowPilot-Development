"""Dependencies for FastAPI routes."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.business import Business
from app.models.user import User
from app.schemas.auth import CurrentUser


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """Extract and validate JWT token from request.
    
    🧨 CRITICAL: Attaches user context to every request
    Used to enforce multi-tenancy (all queries filter by user's business_id)
    
    Raises:
        HTTPException: If token missing, invalid, or expired
    """
    # Prefer Authorization header; fall back to httpOnly access cookie.
    # If header token is malformed/expired but cookie is valid, accept cookie.
    header_token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        header_token = auth_header[7:]
    cookie_token = request.cookies.get("bfp_access")

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

    # Decode and validate token
    payload = None
    for candidate in candidate_tokens:
        try:
            payload = decode_token(candidate)
            break
        except JWTError:
            continue
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject refresh and password-reset tokens — only plain access tokens allowed here
    token_type = payload.get("type")
    if token_type is not None and token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info
    user_id = payload.get("user_id")
    business_id = payload.get("business_id")
    email = payload.get("email")

    if not user_id or not business_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        )

    try:
        user_uuid = UUID(str(user_id))
        business_uuid = UUID(str(business_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
        ) from exc

    # Authoritative role/user state comes from the DB.
    # This prevents stale tokens without role claims from downgrading users to "staff".
    # Joined with Business to resolve organization_id for every request - cheap,
    # and needed by get_org_admin below for cross-subsidiary IT Admin authority.
    row = (
        db.query(User, Business.organization_id)
        .join(Business, Business.id == User.business_id)
        .filter(
            User.id == user_uuid,
            User.business_id == business_uuid,
            User.email == email,
            User.is_active.is_(True),
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user, organization_id = row

    # If the token carries a password fingerprint, reject it when the
    # password has changed since the token was issued. This invalidates
    # all sessions immediately after a password reset or change.
    token_phash = payload.get("phash")
    if token_phash and token_phash != user.hashed_password[-8:]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        user_id=str(user.id),
        business_id=str(user.business_id),
        organization_id=str(organization_id) if organization_id else None,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
    )


def get_org_admin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Dependency that restricts access to users with role='it_admin'.

    🧨 IT Admin authority is scoped by organization_id, not business_id -
    the one sanctioned exception to this codebase's single-tenant filter
    rule (see BaseRepository). Endpoints using this dependency MUST still
    verify `target.organization_id == current_user.organization_id`
    themselves before touching any subsidiary's data.
    """
    if current_user.role != "it_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IT Admin access required",
        )
    return current_user
