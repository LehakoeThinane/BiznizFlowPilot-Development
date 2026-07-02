"""Platform authentication service - business logic for vendor staff auth.

Mirrors AuthService's lockout pattern exactly, but against the fully
separate platform_admins table/token type - never touches `users`.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_platform_access_token,
    create_platform_refresh_token,
    get_platform_token_subject,
    hash_password,
    verify_password,
)
from app.models.platform_admin import PlatformAdmin
from app.repositories.platform_admin import PlatformAdminRepository
from app.schemas.platform import PlatformTokenResponse
from app.services.platform_audit import record_audit


class PlatformAuthService:
    """Platform admin authentication service."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = PlatformAdminRepository(db)

    def login(self, email: str, password: str) -> PlatformTokenResponse:
        """Login a platform admin and return tokens.

        Raises:
            ValueError: If credentials invalid, account locked, or inactive.
        """
        admin = self.repo.get_by_email(email)
        if not admin:
            record_audit(self.db, None, "auth.login", result="failed", meta_data={"email": email})
            self.db.commit()
            raise ValueError("Invalid email or password")

        now = datetime.now(timezone.utc)
        locked_until = admin.locked_until
        if locked_until is not None and locked_until.tzinfo is None:
            # SQLite (used in tests) returns naive datetimes even for tz-aware
            # columns; the column is always stored as UTC.
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until and locked_until > now:
            remaining = int((locked_until - now).total_seconds() / 60) + 1
            record_audit(self.db, admin.id, "auth.login", result="denied", meta_data={"reason": "locked"})
            self.db.commit()
            raise ValueError(
                f"Account locked due to too many failed attempts. "
                f"Try again in {remaining} minute{'s' if remaining != 1 else ''}."
            )

        if not verify_password(password, admin.hashed_password):
            admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
            if admin.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                admin.locked_until = now + self.LOCKOUT_DURATION
            record_audit(self.db, admin.id, "auth.login", result="failed")
            self.db.commit()
            raise ValueError("Invalid email or password")

        if not admin.is_active:
            record_audit(self.db, admin.id, "auth.login", result="denied", meta_data={"reason": "inactive"})
            self.db.commit()
            raise ValueError("Account is inactive")

        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.last_login_at = now
        record_audit(self.db, admin.id, "auth.login", result="success")
        self.db.commit()

        return self._create_tokens(admin)

    def refresh_tokens(self, refresh_token: str) -> PlatformTokenResponse:
        """Issue a new access + refresh token pair from a valid platform refresh token.

        Raises:
            ValueError: If the token is invalid, expired, or the wrong type.
        """
        payload = get_platform_token_subject(refresh_token)
        if not payload or payload.get("type") != "platform_refresh":
            raise ValueError("Invalid or expired refresh token")

        admin_id = payload.get("platform_admin_id")
        if not admin_id:
            raise ValueError("Invalid refresh token payload")

        admin = self.repo.get_by_id(UUID(str(admin_id)))
        if not admin or not admin.is_active:
            raise ValueError("Account not found or inactive")

        token_phash = payload.get("phash")
        if token_phash and token_phash != admin.hashed_password[-8:]:
            raise ValueError("Session invalidated. Please log in again.")

        return self._create_tokens(admin)

    def create_admin(
        self,
        email: str,
        password: str,
        full_name: str,
        platform_role: str = "support",
        impersonation_allowed: bool = False,
        created_by_id: Optional[UUID] = None,
    ) -> PlatformAdmin:
        """Create a new platform admin.

        Raises:
            ValueError: If email already exists.
        """
        existing = self.repo.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")

        admin = PlatformAdmin(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            platform_role=platform_role,
            impersonation_allowed=impersonation_allowed,
            is_active=True,
        )
        self.db.add(admin)
        self.db.flush()

        record_audit(
            self.db,
            created_by_id,
            "platform_admin.create",
            target_type="platform_admin",
            target_id=admin.id,
            meta_data={"email": email, "platform_role": platform_role},
        )
        self.db.commit()
        self.db.refresh(admin)
        return admin

    @staticmethod
    def _create_tokens(admin: PlatformAdmin) -> PlatformTokenResponse:
        """Create access and refresh tokens for a platform admin.

        phash mirrors the tenant-side idiom: a password change immediately
        invalidates all outstanding platform tokens.
        """
        token_data: dict = {
            "sub": str(admin.id),
            "platform_admin_id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "platform_role": admin.platform_role,
            "impersonation_allowed": admin.impersonation_allowed,
            "phash": admin.hashed_password[-8:],
        }

        access_token = create_platform_access_token(token_data)
        refresh_token = create_platform_refresh_token(token_data)

        return PlatformTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.platform_jwt_expiration_hours * 60 * 60,
        )
