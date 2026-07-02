"""Business repository - data access for Business model."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.business import Business
from app.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    """Business repository (tenants)."""

    def __init__(self, db: Session):
        """Initialize with Business model."""
        super().__init__(db, Business)

    def get_by_email(self, email: str) -> Optional[Business]:
        """Get business by email.
        
        Args:
            email: Business email
            
        Returns:
            Business or None
        """
        return self.db.query(Business).filter(
            Business.email == email,
        ).first()

    def get_by_id(self, business_id: UUID) -> Optional[Business]:
        """Get business by ID.
        
        Args:
            business_id: Business ID
            
        Returns:
            Business or None
        """
        return self.db.query(Business).filter(
            Business.id == business_id,
        ).first()
