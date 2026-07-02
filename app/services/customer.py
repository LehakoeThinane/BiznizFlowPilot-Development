"""Customer service - business logic with auto-event emission."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


class CustomerService:
    """Customer service with RBAC.
    
    🧨 RBAC: Owner/Manager can create/edit/delete. Staff can view their assigned customers.
    
    Auto-emits events on create/update/delete when event_service is provided.
    """

    def __init__(self, db: Session, event_service=None):
        """Initialize service.
        
        Args:
            db: SQLAlchemy session
            event_service: Optional EventService for auto-event emission.
                           When None, no events are emitted (backward compatible).
        """
        self.db = db
        self.repo = CustomerRepository(db)
        self._event_service = event_service

    def _emit_event(
        self,
        event_type: EventType,
        business_id: UUID,
        entity_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Emit an event if event_service is available. Never raises."""
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id,
                event_type=event_type,
                entity_type="customer",
                entity_id=entity_id,
                actor_id=actor_id,
                description=description,
                data=data,
            )
        except Exception:
            logger.warning(
                "Failed to emit %s event for customer %s",
                event_type.value,
                entity_id,
                exc_info=True,
            )

    def create(self, business_id: UUID, current_user: CurrentUser, data: CustomerCreate) -> Customer:
        """Create customer.
        
        🧨 RBAC: Only owner/manager can create.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can create customers")

        customer = self.repo.create(business_id=business_id, **data.model_dump())

        self._emit_event(
            event_type=EventType.CUSTOMER_CREATED,
            business_id=business_id,
            entity_id=customer.id,
            actor_id=current_user.user_id,
            description=f"Customer created: '{customer.name}'",
            data={"name": customer.name, "email": customer.email, "company": customer.company},
        )

        return customer

    def get(self, business_id: UUID, current_user: CurrentUser, customer_id: UUID) -> Customer | None:
        """Get customer by ID.
        
        🧨 All roles can view customers in their business.
        """
        return self.repo.get(business_id=business_id, entity_id=customer_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Customer], int]:
        """List customers.
        
        🧨 All roles can view customers in their business.
        """
        customers = self.repo.list(business_id=business_id, skip=skip, limit=limit)
        total = self.repo.count(business_id=business_id)
        return customers, total

    def search(self, business_id: UUID, current_user: CurrentUser, name_part: str, skip: int = 0, limit: int = 100) -> tuple[list[Customer], int]:
        """Search customers by name.
        
        🧨 All roles can search customers in their business.
        """
        customers = self.repo.list_by_name(business_id=business_id, name_part=name_part, skip=skip, limit=limit)
        total = self.repo.count_by_name(business_id=business_id, name_part=name_part)
        return customers, total

    def update(self, business_id: UUID, current_user: CurrentUser, customer_id: UUID, data: CustomerUpdate) -> Customer | None:
        """Update customer.
        
        🧨 RBAC: Only owner/manager can edit.
        """
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied: Only owner/manager can edit customers")

        # Verify customer exists in business before updating
        customer = self.repo.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            return None

        update_data = data.model_dump(exclude_unset=True)
        updated_customer = self.repo.update(business_id=business_id, entity_id=customer_id, **update_data)

        if updated_customer:
            self._emit_event(
                event_type=EventType.CUSTOMER_UPDATED,
                business_id=business_id,
                entity_id=customer_id,
                actor_id=current_user.user_id,
                description=f"Customer updated: '{updated_customer.name}'",
                data={"updated_fields": list(update_data.keys())},
            )

        return updated_customer

    def delete(self, business_id: UUID, current_user: CurrentUser, customer_id: UUID) -> bool:
        """Delete customer.
        
        🧨 RBAC: Only owner can permanently delete.
        """
        if current_user.role != "owner":
            raise ValueError("Permission denied: Only owner can delete customers")

        # Verify customer exists in business before deleting
        customer = self.repo.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            return False

        # Emit event before deletion (entity still exists for context)
        self._emit_event(
            event_type=EventType.CUSTOMER_DELETED,
            business_id=business_id,
            entity_id=customer_id,
            actor_id=current_user.user_id,
            description=f"Customer deleted: '{customer.name}'",
            data={"name": customer.name, "email": customer.email},
        )

        self.repo.delete(business_id=business_id, entity_id=customer_id)
        return True
