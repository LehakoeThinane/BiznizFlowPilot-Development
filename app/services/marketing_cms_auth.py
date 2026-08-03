"""Marketing CMS authentication service - business logic for MM Nexus's own
blog-admin auth.

Mirrors PlatformAuthService's lockout pattern exactly, but against the fully
separate marketing_cms_admins table/token type - never touches `users` or
`platform_admins`. No audit log in v1 (small, fixed set of internal staff);
add one later if this ever needs multi-person accountability.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_marketing_cms_access_token,
    create_marketing_cms_refresh_token,
    get_marketing_cms_token_subject,
    hash_password,
    verify_password,
)
from app.models.marketing_cms_admin import MarketingCmsAdmin
from app.repositories.marketing_cms_admin import MarketingCmsAdminRepository
from app.schemas.marketing_cms import MarketingCmsTokenResponse


class MarketingCmsAuthService:
    """Marketing CMS admin authentication service."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.repo = MarketingCmsAdminRepository(db)

    def login(self, email: str, password: str) -> MarketingCmsTokenResponse:
        """Login a marketing CMS admin and return tokens.

        Raises:
            ValueError: If credentials invalid, account locked, or inactive.
        """
        admin = self.repo.get_by_email(email)
        if not admin:
            raise ValueError("Invalid email or password")

        now = datetime.now(timezone.utc)
        locked_until = admin.locked_until
        if locked_until is not None and locked_until.tzinfo is None:
            # SQLite (used in tests) returns naive datetimes even for tz-aware
            # columns; the column is always stored as UTC.
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until and locked_until > now:
            remaining = int((locked_until - now).total_seconds() / 60) + 1
            raise ValueError(
                f"Account locked due to too many failed attempts. "
                f"Try again in {remaining} minute{'s' if remaining != 1 else ''}."
            )

        if not verify_password(password, admin.hashed_password):
            admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
            if admin.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                admin.locked_until = now + self.LOCKOUT_DURATION
            self.db.commit()
            raise ValueError("Invalid email or password")

        if not admin.is_active:
            raise ValueError("Account is inactive")

        admin.failed_login_attempts = 0
        admin.locked_until = None
        admin.last_login_at = now
        self.db.commit()

        return self._create_tokens(admin)

    def refresh_tokens(self, refresh_token: str) -> MarketingCmsTokenResponse:
        """Issue a new access + refresh token pair from a valid refresh token.

        Raises:
            ValueError: If the token is invalid, expired, or the wrong type.
        """
        payload = get_marketing_cms_token_subject(refresh_token)
        if not payload or payload.get("type") != "marketing_cms_refresh":
            raise ValueError("Invalid or expired refresh token")

        admin_id = payload.get("marketing_cms_admin_id")
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
    ) -> MarketingCmsAdmin:
        """Create a new marketing CMS admin.

        Raises:
            ValueError: If email already exists.
        """
        existing = self.repo.get_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")

        admin = MarketingCmsAdmin(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        return admin

    def change_password(self, marketing_cms_admin_id: UUID, current_password: str, new_password: str) -> None:
        """Change a marketing CMS admin's own password.

        Raises:
            ValueError: If the admin doesn't exist or current_password is wrong.
        """
        admin = self.repo.get_by_id(marketing_cms_admin_id)
        if not admin:
            raise ValueError("Account not found")
        if not verify_password(current_password, admin.hashed_password):
            raise ValueError("Current password is incorrect")

        admin.hashed_password = hash_password(new_password)
        self.db.commit()

    @staticmethod
    def _create_tokens(admin: MarketingCmsAdmin) -> MarketingCmsTokenResponse:
        """Create access and refresh tokens for a marketing CMS admin.

        phash mirrors the tenant/platform idiom: a password change
        immediately invalidates all outstanding tokens.
        """
        token_data: dict = {
            "sub": str(admin.id),
            "marketing_cms_admin_id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "phash": admin.hashed_password[-8:],
        }

        access_token = create_marketing_cms_access_token(token_data)
        refresh_token = create_marketing_cms_refresh_token(token_data)

        return MarketingCmsTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.marketing_cms_jwt_expiration_hours * 60 * 60,
        )
