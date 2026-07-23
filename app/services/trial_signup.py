"""Public, unauthenticated free-trial signup - the missing producer for the
'trial' plan tier.

Every other producer of a trial-tier Organization today is a platform-admin
action (see app/api/platform_admin.py::provision_organization). This service
adds a self-serve equivalent: a visitor supplies an organization name plus
either a password or a Google identity, and gets an instant owner account on
a brand-new, private trial business - no admin, no invite email round trip,
no payment. Deliberately separate from app/services/invitation.py, which
remains the only path real paying-customer accounts go through.
"""

import secrets
from typing import Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.organization import OrganizationService
from app.services.trial_seed import seed_sample_data


class TrialSignupService:
    """Free-trial signup business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def _finish_signup(
        self, organization_name: str, email: str, first_name: str, last_name: str,
        hashed_password: str, auth_provider: str, google_sub: Optional[str],
    ) -> TokenResponse:
        """Shared tail of both signup paths: create org+business+user, seed
        sample data, commit, and mint tokens - all in one transaction."""
        org_service = OrganizationService(self.db)
        shell = org_service.create_organization_shell(
            org_name=organization_name, billing_email=email, plan_tier="trial"
        )

        user = User(
            business_id=shell.business.id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_password,
            role="owner",
            auth_provider=auth_provider,
            google_sub=google_sub,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()

        seed_sample_data(self.db, business_id=shell.business.id, owner_user_id=user.id)

        self.db.commit()
        self.db.refresh(user)

        from app.services.auth import AuthService  # local import avoids a circular import

        return AuthService._create_tokens(
            user_id=user.id,
            business_id=user.business_id,
            email=user.email,
            role=user.role,
            full_name=f"{first_name} {last_name}",
            phash=hashed_password[-8:],
        )

    def create_via_password(
        self, organization_name: str, first_name: str, last_name: str, email: str, password: str,
    ) -> TokenResponse:
        """Sign up with email/password. Raises ValueError if the email is
        already in use anywhere (any business, any auth provider)."""
        if self.user_repo.get_by_email_all(email):
            raise ValueError("An account with this email already exists. Log in instead.")

        hashed_pwd = hash_password(password)
        return self._finish_signup(
            organization_name=organization_name, email=email,
            first_name=first_name, last_name=last_name,
            hashed_password=hashed_pwd, auth_provider="password", google_sub=None,
        )

    def create_via_google(self, organization_name: str, credential: str) -> TokenResponse:
        """Sign up (or log back in) via a Google Identity Services ID token.

        Raises ValueError if the token is invalid/unverified, or if the
        email already belongs to a non-Google account.
        """
        try:
            payload = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), audience=settings.google_client_id
            )
        except ValueError as e:
            raise ValueError("Invalid Google sign-in - please try again.") from e

        if not payload.get("email_verified"):
            raise ValueError("Your Google email address is not verified.")

        google_sub: str = payload["sub"]
        email: str = payload["email"]

        existing = self.user_repo.get_by_google_sub(google_sub)
        if existing:
            from app.services.auth import AuthService  # local import avoids a circular import

            return AuthService._create_tokens(
                user_id=existing.id,
                business_id=existing.business_id,
                email=existing.email,
                role=existing.role,
                full_name=existing.full_name,
                phash=existing.hashed_password[-8:],
            )

        if self.user_repo.get_by_email_all(email):
            raise ValueError("An account with this email already exists. Log in instead.")

        first_name = payload.get("given_name") or email.split("@")[0]
        last_name = payload.get("family_name") or ""
        placeholder_password = hash_password(secrets.token_urlsafe(32))

        try:
            return self._finish_signup(
                organization_name=organization_name, email=email,
                first_name=first_name, last_name=last_name,
                hashed_password=placeholder_password, auth_provider="google", google_sub=google_sub,
            )
        except IntegrityError:
            # Two near-simultaneous requests for the same Google account (e.g.
            # a double-click) can both pass the get_by_google_sub check above
            # before either commits - the loser hits this unique-constraint
            # violation instead of a clean "already exists" result. Recover by
            # rolling back and logging in as the account the winner just created.
            self.db.rollback()
            existing = self.user_repo.get_by_google_sub(google_sub)
            if not existing:
                raise

            from app.services.auth import AuthService  # local import avoids a circular import

            return AuthService._create_tokens(
                user_id=existing.id,
                business_id=existing.business_id,
                email=existing.email,
                role=existing.role,
                full_name=existing.full_name,
                phash=existing.hashed_password[-8:],
            )
