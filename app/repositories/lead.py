"""Lead repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.repositories.base import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    """Lead repository with business_id filtering.
    
    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Lead)

    def get_by_status(self, business_id: UUID, status: str, skip: int = 0, limit: int = 100) -> list[Lead]:
        """Get leads by status within business.
        
        🧨 CRITICAL: Filters by business_id to prevent data leaks.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.status == status,
        ).offset(skip).limit(limit).all()

    def count_by_status(self, business_id: UUID, status: str) -> int:
        """Count leads by status within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.status == status,
        ).count()

    def get_assigned_to(self, business_id: UUID, assigned_to: UUID, skip: int = 0, limit: int = 100) -> list[Lead]:
        """Get leads assigned to user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.assigned_to == assigned_to,
        ).offset(skip).limit(limit).all()

    def count_assigned_to(self, business_id: UUID, assigned_to: UUID) -> int:
        """Count leads assigned to user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.assigned_to == assigned_to,
        ).count()

    def get_by_customer(self, business_id: UUID, customer_id: UUID, skip: int = 0, limit: int = 100) -> list[Lead]:
        """Get leads for customer within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.customer_id == customer_id,
        ).offset(skip).limit(limit).all()

    def count_by_customer(self, business_id: UUID, customer_id: UUID) -> int:
        """Count leads for customer within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Lead).filter(
            Lead.business_id == business_id,
            Lead.customer_id == customer_id,
        ).count()
