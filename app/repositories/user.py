"""User repository - data access for User model."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User repository with multi-tenant filtering."""

    def __init__(self, db: Session):
        """Initialize with User model."""
        super().__init__(db, User)

    def get_by_email(self, business_id, email: str) -> Optional[User]:
        """Get user by email within business.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            email: User email
            
        Returns:
            User or None
        """
        return self.db.query(User).filter(
            User.business_id == business_id,  # 🧨 MULTI-TENANCY
            User.email == email,
        ).first()

    def get_by_email_all(self, email: str) -> Optional[User]:
        """Get user by email across all tenants.

        ⚠️ Used only for login (before checking business_id)

        Args:
            email: User email

        Returns:
            User or None
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_google_sub(self, google_sub: str) -> Optional[User]:
        """Get user by Google account subject ID, across all tenants.

        Used to recognize a returning trial-signup user logging back in
        via Google, before any business_id is known.

        Args:
            google_sub: Google account subject ID

        Returns:
            User or None
        """
        return self.db.query(User).filter(User.google_sub == google_sub).first()

    def list_by_role(self, business_id, role: str) -> list[User]:
        """List users with specific role in business.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            role: User role
            
        Returns:
            List of users
        """
        return self.db.query(User).filter(
            User.business_id == business_id,  # 🧨 MULTI-TENANCY
            User.role == role,
        ).all()

    def count_by_role(self, business_id, role: str) -> int:
        """Count users with specific role in business.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            role: User role
            
        Returns:
            Count of users
        """
        return self.db.query(User).filter(
            User.business_id == business_id,  # 🧨 MULTI-TENANCY
            User.role == role,
        ).count()

    def count_active_in_organization(self, organization_id: UUID) -> int:
        """Count active users across every subsidiary in an organization.

        🧨 Deliberately bypasses the single-business_id filter for an
        org-wide aggregate - same sanctioned exception as
        InvitationRepository.list_for_organization. Used for seat-limit
        enforcement, which is a per-organization (not per-business) cap.
        """
        return (
            self.db.query(User)
            .join(Business, Business.id == User.business_id)
            .filter(Business.organization_id == organization_id, User.is_active.is_(True))
            .count()
        )
