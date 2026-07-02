"""Purchase order service - business logic with auto-event emission."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models.purchase_order import PurchaseOrder
from app.repositories.purchase_order import PurchaseOrderRepository
from app.schemas.purchase_order import POCreate, POUpdate
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)


class PurchaseOrderService:
    """Purchase order service with RBAC."""

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = PurchaseOrderRepository(db)
        self._event_service = event_service

    def _emit_event(self, event_type: EventType, business_id: UUID, entity_id: UUID, actor_id: UUID | None = None, description: str | None = None, data: dict | None = None) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id, event_type=event_type, entity_type="purchase_order",
                entity_id=entity_id, actor_id=actor_id, description=description, data=data
            )
        except Exception:
            logger.warning("Failed to emit %s event", event_type.value, exc_info=True)

    def create(self, business_id: UUID, current_user: CurrentUser, data: POCreate) -> PurchaseOrder:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied")

        po_data = data.model_dump(exclude={"line_items"})
        po = self.repo.create(business_id=business_id, **po_data)

        for item in data.line_items:
            self.repo.create_line_item(po_id=po.id, **item.model_dump())

        self._emit_event(
            event_type=EventType.PURCHASE_ORDER_CREATED,
            business_id=business_id,
            entity_id=po.id,
            actor_id=current_user.user_id,
            description=f"Purchase order {po.po_number} created",
            data={"po_number": po.po_number, "total_cost": float(po.total_cost)}
        )

        return po

    def get(self, business_id: UUID, current_user: CurrentUser, po_id: UUID) -> PurchaseOrder | None:
        return self.repo.get(business_id=business_id, entity_id=po_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[PurchaseOrder], int]:
        return self.repo.list(business_id=business_id, skip=skip, limit=limit), self.repo.count(business_id=business_id)

    def update(self, business_id: UUID, current_user: CurrentUser, po_id: UUID, data: POUpdate) -> PurchaseOrder | None:
        if current_user.role not in ["owner", "manager"]:
            raise ValueError("Permission denied")

        po = self.repo.get(business_id=business_id, entity_id=po_id)
        if not po:
            return None

        old_status = po.status
        updated_po = self.repo.update(business_id=business_id, entity_id=po_id, **data.model_dump(exclude_unset=True))

        if updated_po and data.status and data.status != old_status:
            event_type = EventType.PURCHASE_ORDER_CREATED
            if data.status == "sent":
                event_type = EventType.PURCHASE_ORDER_SENT
            elif data.status == "received":
                event_type = EventType.PURCHASE_ORDER_RECEIVED
                
            self._emit_event(
                event_type=event_type,
                business_id=business_id,
                entity_id=po_id,
                actor_id=current_user.user_id,
                description=f"Purchase order status changed to {data.status}",
                data={"old_status": old_status, "new_status": data.status}
            )

        return updated_po
