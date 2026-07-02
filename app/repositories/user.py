"""User repository - data access for User model."""

from typing import Optional

from sqlalchemy.orm import Session

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
