"""Purchase requisition service - submit/approve/reject/convert-to-PO with auto-event emission."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import ALL_BUSINESS_ROLES, PRIVILEGED_ROLES, require_role
from app.models.purchase_requisition import PurchaseRequisition
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.purchase_requisition import PurchaseRequisitionRepository
from app.schemas.auth import CurrentUser
from app.schemas.purchase_requisition import PRCreate, PRStatusUpdate
from app.utils.notify import notify_business


class PurchaseRequisitionService:
    """Purchase requisition service with RBAC and atomic event emission."""

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = PurchaseRequisitionRepository(db)
        self._po_repo = PurchaseOrderRepository(db)
        self._event_service = event_service

    def _emit_event(self, event_type: EventType, business_id: UUID, entity_id: UUID, actor_id: UUID | None = None, description: str | None = None, data: dict | None = None, entity_type: str = "purchase_requisition") -> None:
        """Queue an event row in the same (not-yet-committed) transaction as
        the caller's pending business-row change - the caller commits once,
        after this call, so both persist atomically or neither does."""
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id, event_type=event_type, entity_type=entity_type,
            entity_id=entity_id, actor_id=actor_id, description=description, data=data,
            commit=False,
        )

    def create(self, business_id: UUID, current_user: CurrentUser, data: PRCreate) -> PurchaseRequisition:
        require_role(current_user, ALL_BUSINESS_ROLES, "submit purchase requisitions")

        pr_data = data.model_dump(exclude={"line_items"})
        pr = self.repo.create(
            business_id=business_id, requested_by=current_user.user_id, commit=False, **pr_data
        )

        for item in data.line_items:
            self.repo.create_line_item(requisition_id=pr.id, commit=False, **item.model_dump())

        notify_business(
            self.db, business_id, "order_status",
            "Purchase requisition submitted",
            f"{current_user.full_name} requested to purchase: {pr.title}",
            action_url="/purchasing/requisitions", related_type="purchase_requisition", related_id=pr.id,
        )

        self._emit_event(
            event_type=EventType.PURCHASE_REQUISITION_CREATED,
            business_id=business_id,
            entity_id=pr.id,
            actor_id=current_user.user_id,
            description=f"Purchase requisition submitted: {pr.title}",
            data={"title": pr.title, "estimated_total": float(pr.estimated_total)},
        )

        self.db.commit()
        self.db.refresh(pr)
        return pr

    def get(self, business_id: UUID, current_user: CurrentUser, pr_id: UUID) -> PurchaseRequisition | None:
        return self.repo.get(business_id=business_id, entity_id=pr_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[PurchaseRequisition], int]:
        return self.repo.list(business_id=business_id, skip=skip, limit=limit), self.repo.count(business_id=business_id)

    def update_status(self, business_id: UUID, current_user: CurrentUser, pr_id: UUID, data: PRStatusUpdate) -> PurchaseRequisition | None:
        require_role(current_user, PRIVILEGED_ROLES, "approve or reject purchase requisitions")

        pr = self.repo.get(business_id=business_id, entity_id=pr_id)
        if not pr:
            return None
        if pr.status != "pending":
            raise ValueError(f"Cannot change status of a requisition that is already '{pr.status}'")

        updates: dict = {"status": data.status}
        if data.status == "approved":
            updates["approved_by"] = current_user.user_id
            updates["approved_at"] = datetime.now(timezone.utc)
        elif data.status == "rejected":
            updates["rejection_reason"] = data.rejection_reason

        updated_pr = self.repo.update(business_id=business_id, entity_id=pr_id, commit=False, **updates)

        notify_business(
            self.db, business_id, "order_status",
            f"Purchase requisition {data.status}",
            f"'{pr.title}' was {data.status}.",
            action_url="/purchasing/requisitions", related_type="purchase_requisition", related_id=pr_id,
        )

        self._emit_event(
            event_type=EventType.PURCHASE_REQUISITION_STATUS_CHANGED,
            business_id=business_id,
            entity_id=pr_id,
            actor_id=current_user.user_id,
            description=f"Purchase requisition '{pr.title}' {data.status}",
            data={"old_status": "pending", "new_status": data.status},
        )

        self.db.commit()
        self.db.refresh(updated_pr)
        return updated_pr

    def convert_to_purchase_order(self, business_id: UUID, current_user: CurrentUser, pr_id: UUID):
        """Turn an approved requisition into a real, sendable PurchaseOrder."""
        require_role(current_user, PRIVILEGED_ROLES, "convert purchase requisitions")

        pr = self.repo.get(business_id=business_id, entity_id=pr_id)
        if not pr:
            return None
        if pr.status != "approved":
            raise ValueError("Only an approved requisition can be converted to a purchase order")

        subtotal = Decimal("0.00")
        line_items_data = []
        for item in pr.line_items:
            unit_cost = item.estimated_unit_cost or Decimal("0.00")
            item_subtotal = unit_cost * item.quantity
            subtotal += item_subtotal
            line_items_data.append({
                "product_id": item.product_id,
                "quantity_ordered": item.quantity,
                "unit_cost": unit_cost,
                "subtotal": item_subtotal,
            })

        po = self._po_repo.create(
            business_id=business_id,
            commit=False,
            po_number=f"REQ-{pr.id.hex[:8].upper()}",
            supplier_id=pr.supplier_id,
            status="draft",
            subtotal=subtotal,
            total_cost=subtotal,
            notes=f"Converted from purchase requisition: {pr.title}",
            meta_data={"source_requisition_id": str(pr.id)},
            created_by=current_user.user_id,
        )
        for item_data in line_items_data:
            self._po_repo.create_line_item(po_id=po.id, commit=False, **item_data)

        updated_pr = self.repo.update(
            business_id=business_id, entity_id=pr_id, commit=False,
            status="converted", converted_purchase_order_id=po.id,
        )

        self._emit_event(
            event_type=EventType.PURCHASE_ORDER_CREATED,
            business_id=business_id,
            entity_id=po.id,
            actor_id=current_user.user_id,
            description=f"Purchase order {po.po_number} created from requisition '{pr.title}'",
            data={"po_number": po.po_number, "total_cost": float(po.total_cost), "source_requisition_id": str(pr.id)},
            entity_type="purchase_order",
        )
        self._emit_event(
            event_type=EventType.PURCHASE_REQUISITION_STATUS_CHANGED,
            business_id=business_id,
            entity_id=pr_id,
            actor_id=current_user.user_id,
            description=f"Purchase requisition '{pr.title}' converted to purchase order {po.po_number}",
            data={"old_status": "approved", "new_status": "converted"},
        )

        self.db.commit()
        self.db.refresh(updated_pr)
        self.db.refresh(po)
        return updated_pr, po
