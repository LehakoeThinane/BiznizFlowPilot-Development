"""Customer repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Customer repository with business_id filtering.
    
    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Customer)

    def get_by_email(self, business_id: UUID, email: str) -> Customer | None:
        """Get customer by email within business.
        
        🧨 CRITICAL: Filters by business_id to prevent data leaks.
        """
        return self.db.query(Customer).filter(
            Customer.business_id == business_id,
            Customer.email == email,
        ).first()

    def list_by_name(self, business_id: UUID, name_part: str, skip: int = 0, limit: int = 100) -> list[Customer]:
        """Search customers by name within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Customer).filter(
            Customer.business_id == business_id,
            Customer.name.ilike(f"%{name_part}%"),
        ).offset(skip).limit(limit).all()

    def count_by_name(self, business_id: UUID, name_part: str) -> int:
        """Count customers matching name within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Customer).filter(
            Customer.business_id == business_id,
            Customer.name.ilike(f"%{name_part}%"),
        ).count()
