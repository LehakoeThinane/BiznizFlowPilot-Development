"""Security utilities: JWT, password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ============================================================================
# Password Hashing
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ============================================================================
# JWT Token Management
# ============================================================================


def create_access_token(
    subject: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=settings.jwt_expiration_hours
        )

    to_encode = {**subject, "exp": expire}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_refresh_token(
    subject: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create JWT refresh token with longer expiration."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expiration_days
        )

    to_encode = {**subject, "exp": expire, "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_password_reset_token(
    subject: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create short-lived password reset token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_token_expiration_minutes
        )

    to_encode = {**subject, "exp": expire, "type": "password_reset"}
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token.

    Raises:
        JWTError: If token is invalid or expired
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return payload


def get_token_subject(token: str) -> Optional[dict[str, Any]]:
    """Get subject from token. Returns None if token is invalid."""
    try:
        payload = decode_token(token)
        return payload
    except JWTError:
        return None


# ============================================================================
# Platform (vendor staff) JWT Management
#
# Signed with a distinct key (settings.effective_platform_secret_key) and
# carry "platform_access"/"platform_refresh" type claims, so these tokens can
# never be mistaken for - or forged from - a tenant access/refresh token even
# though decode_token() shares the same HS256 algorithm.
# ============================================================================


def create_platform_access_token(
    subject: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a platform-admin JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=settings.platform_jwt_expiration_hours
        )

    to_encode = {**subject, "exp": expire, "type": "platform_access"}
    return jwt.encode(
        to_encode,
        settings.effective_platform_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_platform_refresh_token(
    subject: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a platform-admin JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.platform_refresh_token_expiration_days
        )

    to_encode = {**subject, "exp": expire, "type": "platform_refresh"}
    return jwt.encode(
        to_encode,
        settings.effective_platform_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_platform_token(token: str) -> dict[str, Any]:
    """Decode and validate a platform-admin JWT token.

    Raises:
        JWTError: If token is invalid or expired
    """
    return jwt.decode(
        token,
        settings.effective_platform_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def get_platform_token_subject(token: str) -> Optional[dict[str, Any]]:
    """Get subject from a platform token. Returns None if invalid."""
    try:
        return decode_platform_token(token)
    except JWTError:
        return None
