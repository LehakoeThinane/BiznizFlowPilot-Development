"""Purchase requisition repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionLineItem
from app.repositories.base import BaseRepository


class PurchaseRequisitionRepository(BaseRepository[PurchaseRequisition]):
    """Purchase requisition repository with business_id filtering."""

    def __init__(self, db: Session):
        super().__init__(db, PurchaseRequisition)

    def get_by_status(self, business_id: UUID, status: str, skip: int = 0, limit: int = 100) -> list[PurchaseRequisition]:
        """Get purchase requisitions by status within business."""
        return self.db.query(PurchaseRequisition).filter(
            PurchaseRequisition.business_id == business_id,
            PurchaseRequisition.status == status,
        ).offset(skip).limit(limit).all()

    def create_line_item(self, commit: bool = True, **kwargs) -> PurchaseRequisitionLineItem:
        """Create a line item for a purchase requisition.

        Args:
            commit: When False, flush instead of commit - lets the caller
                batch this into a larger atomic transaction.
        """
        line_item = PurchaseRequisitionLineItem(**kwargs)
        self.db.add(line_item)
        if commit:
            self.db.commit()
            self.db.refresh(line_item)
        else:
            self.db.flush()
        return line_item
