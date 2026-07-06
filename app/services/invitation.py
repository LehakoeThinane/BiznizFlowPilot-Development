"""Invitation service - domain-restricted employee onboarding."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.models.user_invitation import UserInvitation
from app.repositories.invitation import InvitationRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.auth import TokenResponse


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class InvitationService:
    """Invitation business logic."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.invite_repo = InvitationRepository(db)
        self.org_repo = OrganizationRepository(db)

    def create_invitation(
        self,
        business_id: UUID,
        organization_id: UUID,
        email: str,
        role: str,
        invited_by: UUID,
        inviter_role: str,
        inviter_name: str,
        commit: bool = True,
    ) -> tuple[UserInvitation, str]:
        """Create a pending invitation and return (row, raw_token) for emailing.

        Args:
            commit: When False, flush instead of commit - lets the caller
                batch this into a larger atomic transaction (e.g. together
                with an Event row, for outbox-style atomicity). Defaults to
                True, matching prior behavior exactly.

        Raises:
            ValueError: If the email's domain isn't authorized for this
                organization, a pending invite already exists, the email
                already belongs to an active user, or a non-it_admin tries
                to mint an it_admin invite.
        """
        if role == "it_admin" and inviter_role not in ("owner", "it_admin"):
            raise ValueError("Only an owner or an existing IT Admin can invite another IT Admin")

        if not self.org_repo.domain_is_authorized(organization_id, email):
            raise ValueError("This email domain is not authorized for this organization")

        existing_user = self.db.query(User).filter(User.email == email).first()
        if existing_user:
            raise ValueError("An account with this email already exists")

        existing_invite = self.invite_repo.get_pending_for_business_email(business_id, email)
        if existing_invite:
            raise ValueError("A pending invitation already exists for this email")

        raw_token = secrets.token_urlsafe(32)
        invitation = UserInvitation(
            business_id=business_id,
            organization_id=organization_id,
            email=email,
            role=role,
            invited_by=invited_by,
            token_hash=_hash_token(raw_token),
            status="pending",
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.invite_token_expiration_days),
        )
        self.db.add(invitation)
        if commit:
            self.db.commit()
            self.db.refresh(invitation)
        else:
            self.db.flush()

        return invitation, raw_token

    def revoke_invitation(
        self,
        invitation_id: UUID,
        business_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> bool:
        """Revoke a pending invitation.

        Scoped by business_id (owner/manager - their own business only) or
        organization_id (it_admin - any subsidiary in their org). Exactly
        one of the two should be passed by the caller.
        """
        query = self.db.query(UserInvitation).filter(UserInvitation.id == invitation_id)
        if business_id is not None:
            query = query.filter(UserInvitation.business_id == business_id)
        if organization_id is not None:
            query = query.filter(UserInvitation.organization_id == organization_id)

        invitation = query.first()
        if not invitation or invitation.status != "pending":
            return False

        invitation.status = "revoked"
        self.db.commit()
        return True

    def validate_token(self, raw_token: str) -> UserInvitation:
        """Validate a raw invite token, raising ValueError if invalid/expired/resolved."""
        invitation = self.invite_repo.get_by_token_hash(_hash_token(raw_token))
        if not invitation:
            raise ValueError("Invalid invitation")
        if invitation.status != "pending":
            raise ValueError("This invitation is no longer valid")
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            # Some drivers (e.g. SQLite) return naive datetimes even for
            # timezone-aware columns; the column is always stored as UTC.
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            invitation.status = "expired"
            self.db.commit()
            raise ValueError("This invitation has expired")
        return invitation

    def accept_invitation(
        self,
        raw_token: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> TokenResponse:
        """Accept a valid invitation, creating the User and returning tokens."""
        from app.services.auth import AuthService  # local import avoids a circular import

        invitation = self.validate_token(raw_token)

        # Defense in depth: re-validate domain in case the org's domains
        # changed since the invite was sent.
        if not self.org_repo.domain_is_authorized(invitation.organization_id, invitation.email):
            raise ValueError("This email domain is no longer authorized for this organization")

        existing_user = self.db.query(User).filter(User.email == invitation.email).first()
        if existing_user:
            raise ValueError("An account with this email already exists")

        hashed_pwd = hash_password(password)
        user = User(
            business_id=invitation.business_id,
            email=invitation.email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_pwd,
            role=invitation.role,
            is_active=True,
        )
        self.db.add(user)

        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)

        return AuthService._create_tokens(
            user_id=user.id,
            business_id=user.business_id,
            email=user.email,
            role=user.role,
            full_name=f"{first_name} {last_name}",
            phash=hashed_pwd[-8:],
        )

    def get_display_context(self, invitation: UserInvitation) -> tuple[str, str]:
        """Return (organization_name, business_name) for the validate-invite page."""
        business = self.db.query(Business).filter(Business.id == invitation.business_id).first()
        organization = (
            self.db.query(Organization)
            .filter(Organization.id == invitation.organization_id)
            .first()
        )
        return (
            organization.name if organization else "",
            business.name if business else "",
        )
