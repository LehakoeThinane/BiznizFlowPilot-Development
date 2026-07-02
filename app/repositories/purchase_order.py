"""Purchase order repository - data access layer."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.purchase_order import PurchaseOrder, PurchaseOrderLineItem
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    """Purchase order repository with business_id filtering."""

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, PurchaseOrder)

    def get_by_po_number(self, business_id: UUID, po_number: str) -> Optional[PurchaseOrder]:
        """Get purchase order by PO number within business."""
        return self.db.query(PurchaseOrder).filter(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.po_number == po_number,
        ).first()

    def get_by_status(self, business_id: UUID, status: str, skip: int = 0, limit: int = 100) -> list[PurchaseOrder]:
        """Get purchase orders by status within business."""
        return self.db.query(PurchaseOrder).filter(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.status == status,
        ).offset(skip).limit(limit).all()

    def get_by_supplier(self, business_id: UUID, supplier_id: UUID, skip: int = 0, limit: int = 100) -> list[PurchaseOrder]:
        """Get purchase orders by supplier within business."""
        return self.db.query(PurchaseOrder).filter(
            PurchaseOrder.business_id == business_id,
            PurchaseOrder.supplier_id == supplier_id,
        ).offset(skip).limit(limit).all()

    def create_line_item(self, **kwargs) -> PurchaseOrderLineItem:
        """Create a line item for a purchase order."""
        line_item = PurchaseOrderLineItem(**kwargs)
        self.db.add(line_item)
        self.db.commit()
        self.db.refresh(line_item)
        return line_item
