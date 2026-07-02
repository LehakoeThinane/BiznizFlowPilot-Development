"""Base repository with multi-tenant filtering - THE FOUNDATION OF SECURITY."""

from typing import Generic, Optional, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Base repository with multi-tenant support.
    
    🧨 CRITICAL: Every query must filter by business_id
    Forgetting this = data leak across companies
    """

    def __init__(self, db: Session, model: type[T]):
        """Initialize repository.
        
        Args:
            db: SQLAlchemy session
            model: Model class
        """
        self.db = db
        self.model = model

    def create(self, business_id: UUID, **kwargs) -> T:
        """Create entity in specified business.
        
        Args:
            business_id: Tenant ID (MUST be set)
            **kwargs: Entity attributes
            
        Returns:
            Created entity
        """
        # Ensure business_id is set on the entity
        kwargs["business_id"] = business_id
        
        entity = self.model(**kwargs)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def get(self, business_id: UUID, entity_id: UUID) -> Optional[T]:
        """Get entity by ID within tenant.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            entity_id: Entity ID
            
        Returns:
            Entity or None
        """
        return self.db.query(self.model).filter(
            self.model.id == entity_id,
            self.model.business_id == business_id,  # 🧨 MULTI-TENANCY ENFORCEMENT
        ).first()

    def list(self, business_id: UUID, skip: int = 0, limit: int = 20) -> list[T]:
        """List entities for tenant.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of entities
        """
        return self.db.query(self.model).filter(
            self.model.business_id == business_id  # 🧨 MULTI-TENANCY ENFORCEMENT
        ).offset(skip).limit(limit).all()

    def count(self, business_id: UUID) -> int:
        """Count entities for tenant.
        
        🧨 CRITICAL: Filters by business_id
        
        Args:
            business_id: Tenant ID
            
        Returns:
            Count of entities
        """
        return self.db.query(self.model).filter(
            self.model.business_id == business_id  # 🧨 MULTI-TENANCY ENFORCEMENT
        ).count()

    def update(self, business_id: UUID, entity_id: UUID, **kwargs) -> Optional[T]:
        """Update entity within tenant.
        
        🧨 CRITICAL: Filters by business_id before updating
        
        Args:
            business_id: Tenant ID
            entity_id: Entity ID
            **kwargs: Updated attributes
            
        Returns:
            Updated entity or None
        """
        entity = self.get(business_id, entity_id)
        if not entity:
            return None
            
        for key, value in kwargs.items():
            setattr(entity, key, value)
            
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, business_id: UUID, entity_id: UUID) -> bool:
        """Delete entity within tenant.
        
        🧨 CRITICAL: Filters by business_id before deleting
        
        Args:
            business_id: Tenant ID
            entity_id: Entity ID
            
        Returns:
            True if deleted, False if not found
        """
        entity = self.get(business_id, entity_id)
        if not entity:
            return False
            
        self.db.delete(entity)
        self.db.commit()
        return True

    def commit(self) -> None:
        """Commit current transaction."""
        self.db.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self.db.rollback()
