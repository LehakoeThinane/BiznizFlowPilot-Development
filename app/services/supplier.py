"""Supplier service - business logic with auto-event emission."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


class SupplierService:
    """Supplier service with RBAC and auto-event emission.

    🧨 RBAC: Owner/Manager can create/update/delete. Staff can view.
    """

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = SupplierRepository(db)
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
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id,
                event_type=event_type,
                entity_type="supplier",
                entity_id=entity_id,
                actor_id=actor_id,
                description=description,
                data=data,
            )
        except Exception:
            logger.warning(
                "Failed to emit %s event for supplier %s",
                event_type.value,
                entity_id,
                exc_info=True,
            )

    def create(self, business_id: UUID, current_user: CurrentUser, data: SupplierCreate) -> Supplier:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied")

        supplier = self.repo.create(business_id=business_id, **data.model_dump())

        self._emit_event(
            event_type=EventType.SUPPLIER_CREATED,
            business_id=business_id,
            entity_id=supplier.id,
            actor_id=current_user.user_id,
            description=f"Supplier '{supplier.name}' created",
            data={"code": supplier.code},
        )

        return supplier

    def get(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID) -> Supplier | None:
        return self.repo.get(business_id=business_id, entity_id=supplier_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Supplier], int]:
        return self.repo.list(business_id=business_id, skip=skip, limit=limit), self.repo.count(business_id=business_id)

    def update(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID, data: SupplierUpdate) -> Supplier | None:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied")

        update_data = data.model_dump(exclude_unset=True)
        supplier = self.repo.update(business_id=business_id, entity_id=supplier_id, **update_data)

        if supplier:
            self._emit_event(
                event_type=EventType.SUPPLIER_UPDATED,
                business_id=business_id,
                entity_id=supplier_id,
                actor_id=current_user.user_id,
                description="Supplier updated",
                data={"updated_fields": list(update_data.keys())},
            )

        return supplier

    def delete(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID) -> bool:
        if current_user.role != "owner":
            raise ValueError("Permission denied")

        supplier = self.repo.get(business_id=business_id, entity_id=supplier_id)
        if not supplier:
            return False

        self._emit_event(
            event_type=EventType.SUPPLIER_DELETED,
            business_id=business_id,
            entity_id=supplier_id,
            actor_id=current_user.user_id,
            description=f"Supplier '{supplier.name}' deleted",
            data={"code": supplier.code},
        )

        self.repo.delete(business_id=business_id, entity_id=supplier_id)
        return True
