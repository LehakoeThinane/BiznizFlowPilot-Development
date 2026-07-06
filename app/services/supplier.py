"""Supplier service - business logic with auto-event emission."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import OWNER_ONLY, PRIVILEGED_ROLES, require_role
from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.schemas.auth import CurrentUser


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
        self._event_service.create_event(
            business_id=business_id,
            event_type=event_type,
            entity_type="supplier",
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            data=data,
            commit=False,
        )

    def create(self, business_id: UUID, current_user: CurrentUser, data: SupplierCreate) -> Supplier:
        require_role(current_user, PRIVILEGED_ROLES, "create suppliers")

        supplier = self.repo.create(business_id=business_id, commit=False, **data.model_dump())

        self._emit_event(
            event_type=EventType.SUPPLIER_CREATED,
            business_id=business_id,
            entity_id=supplier.id,
            actor_id=current_user.user_id,
            description=f"Supplier '{supplier.name}' created",
            data={"code": supplier.code},
        )

        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def get(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID) -> Supplier | None:
        return self.repo.get(business_id=business_id, entity_id=supplier_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Supplier], int]:
        return self.repo.list(business_id=business_id, skip=skip, limit=limit), self.repo.count(business_id=business_id)

    def update(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID, data: SupplierUpdate) -> Supplier | None:
        require_role(current_user, PRIVILEGED_ROLES, "update suppliers")

        update_data = data.model_dump(exclude_unset=True)
        supplier = self.repo.update(business_id=business_id, entity_id=supplier_id, commit=False, **update_data)

        if supplier:
            self._emit_event(
                event_type=EventType.SUPPLIER_UPDATED,
                business_id=business_id,
                entity_id=supplier_id,
                actor_id=current_user.user_id,
                description="Supplier updated",
                data={"updated_fields": list(update_data.keys())},
            )
            self.db.commit()
            self.db.refresh(supplier)

        return supplier

    def delete(self, business_id: UUID, current_user: CurrentUser, supplier_id: UUID) -> bool:
        require_role(current_user, OWNER_ONLY, "delete suppliers")

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

        self.repo.delete(business_id=business_id, entity_id=supplier_id, commit=False)
        self.db.commit()
        return True
