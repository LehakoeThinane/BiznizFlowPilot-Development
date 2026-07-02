"""Authentication service - business logic for auth."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    get_token_subject,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.organization import OrganizationService


class AuthService:
    """Authentication service."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.user_repo = UserRepository(db)

    def register(
        self,
        business_name: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> TokenResponse:
        """Register new organization (client account), its first subsidiary business, and owner.

        Creates:
        1. Organization (client account) + first subsidiary Business
        2. User (owner with full access)
        3. Returns tokens

        Args:
            business_name: Business/organization name
            email: Owner email (also used as business/organization billing email)
            password: Owner password
            first_name: Owner first name
            last_name: Owner last name

        Returns:
            TokenResponse with access and refresh tokens

        Raises:
            ValueError: If email already exists
        """
        org_service = OrganizationService(self.db)
        try:
            provisioned = org_service.create_organization_with_first_subsidiary(
                org_name=business_name,
                billing_email=email,
                owner_email=email,
                owner_password=password,
                owner_first_name=first_name,
                owner_last_name=last_name,
                plan_tier="trial",
            )
            self.db.commit()

            # Generate tokens
            return self._create_tokens(
                user_id=provisioned.owner.id,
                business_id=provisioned.business.id,
                email=email,
                role="owner",
                full_name=f"{first_name} {last_name}",
                phash=provisioned.owner.hashed_password[-8:],
            )

        except Exception as e:
            self.db.rollback()
            raise e

    # Number of consecutive failures before the account is locked
    MAX_FAILED_ATTEMPTS = 5
    # How long the account stays locked after hitting the limit
    LOCKOUT_DURATION = timedelta(minutes=15)

    def login(self, email: str, password: str) -> TokenResponse:
        """Login user and return tokens.

        Raises:
            ValueError: If credentials invalid or account is locked.
        """
        user = self.user_repo.get_by_email_all(email)
        if not user:
            raise ValueError("Invalid email or password")

        # Check lockout before doing anything else
        now = datetime.now(timezone.utc)
        if user.locked_until and user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() / 60) + 1
            raise ValueError(
                f"Account locked due to too many failed attempts. "
                f"Try again in {remaining} minute{'s' if remaining != 1 else ''}."
            )

        # Verify password
        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.locked_until = now + self.LOCKOUT_DURATION
            self.db.commit()
            raise ValueError("Invalid email or password")

        # Check user is active
        if not user.is_active:
            raise ValueError("User account is inactive")

        # Successful login — clear any previous failure state
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()

        return self._create_tokens(
            user_id=user.id,
            business_id=user.business_id,
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            phash=user.hashed_password[-8:],
        )

    def validate_user(
        self,
        user_id: UUID,
        business_id: UUID,
    ) -> Optional[User]:
        """Validate user exists and is active.
        
        🧨 CRITICAL: Used to extract user from JWT token
        Ensures user still exists and is in the business
        
        Args:
            user_id: User ID
            business_id: Business ID
            
        Returns:
            User if valid, None otherwise
        """
        user = self.user_repo.get(business_id, user_id)
        
        if not user or not user.is_active:
            return None
            
        return user

    def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """Issue a new access + refresh token pair from a valid refresh token.

        Raises:
            ValueError: If the token is invalid, expired, or the wrong type.
        """
        payload = get_token_subject(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid or expired refresh token")

        user_id = payload.get("user_id") or payload.get("sub")
        business_id = payload.get("business_id")
        if not user_id or not business_id:
            raise ValueError("Invalid refresh token payload")

        user = self.validate_user(UUID(str(user_id)), UUID(str(business_id)))
        if not user:
            raise ValueError("User account not found or inactive")

        return self._create_tokens(
            user_id=user.id,
            business_id=user.business_id,
            email=user.email,
            role=user.role,
            full_name=user.full_name or "",
            phash=user.hashed_password[-8:],
        )

    def request_password_reset(self, email: str) -> str:
        """Create a password reset token for an existing active user."""
        user = self.user_repo.get_by_email_all(email)
        if not user:
            raise ValueError("User with this email was not found")
        if not user.is_active:
            raise ValueError("User account is inactive")

        # phash is a fingerprint of the current password hash.
        # Once the password is reset the fingerprint changes, making
        # any previously issued reset token immediately invalid (one-time use).
        return create_password_reset_token(
            {
                "sub": str(user.id),
                "user_id": str(user.id),
                "business_id": str(user.business_id),
                "email": user.email,
                "phash": user.hashed_password[-8:],
            }
        )

    def reset_password(self, token: str, new_password: str) -> None:
        """Reset a user's password using a valid password reset token."""
        payload = get_token_subject(token)
        if not payload or payload.get("type") != "password_reset":
            raise ValueError("Invalid or expired reset token")

        user_id = payload.get("user_id") or payload.get("sub")
        business_id = payload.get("business_id")
        if not user_id or not business_id:
            raise ValueError("Invalid reset token payload")

        user = self.validate_user(UUID(str(user_id)), UUID(str(business_id)))
        if not user:
            raise ValueError("Invalid reset token user")

        # Enforce one-time use: reject if the password has already changed
        # since this token was issued (fingerprint mismatch).
        token_phash = payload.get("phash")
        if token_phash and token_phash != user.hashed_password[-8:]:
            raise ValueError("Invalid or expired reset token")

        user.hashed_password = hash_password(new_password)
        self.db.add(user)
        self.db.commit()

    @staticmethod
    def _create_tokens(
        user_id: UUID,
        business_id: UUID,
        email: str,
        role: str = "staff",
        full_name: str = "",
        phash: str = "",
    ) -> TokenResponse:
        """Create access and refresh tokens.

        phash is the last 8 chars of the user's bcrypt hash. Including it in
        both token types means any password change (reset or manual) immediately
        invalidates all outstanding access and refresh tokens.
        """
        token_data: dict = {
            "sub": str(user_id),
            "user_id": str(user_id),
            "business_id": str(business_id),
            "email": email,
            "role": role,
            "full_name": full_name,
        }
        if phash:
            token_data["phash"] = phash

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=24 * 60 * 60,
        )
