"""Sales order repository - data access layer."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.sales_order import OrderLineItem, SalesOrder
from app.repositories.base import BaseRepository


class SalesOrderRepository(BaseRepository[SalesOrder]):
    """Sales order repository with business_id filtering."""

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, SalesOrder)

    def get_by_order_number(self, business_id: UUID, order_number: str) -> Optional[SalesOrder]:
        """Get sales order by order number within business."""
        return self.db.query(SalesOrder).filter(
            SalesOrder.business_id == business_id,
            SalesOrder.order_number == order_number,
        ).first()

    def get_by_status(self, business_id: UUID, status: str, skip: int = 0, limit: int = 100) -> list[SalesOrder]:
        """Get sales orders by status within business."""
        return self.db.query(SalesOrder).filter(
            SalesOrder.business_id == business_id,
            SalesOrder.status == status,
        ).offset(skip).limit(limit).all()

    def get_by_customer(self, business_id: UUID, customer_id: UUID, skip: int = 0, limit: int = 100) -> list[SalesOrder]:
        """Get sales orders by customer within business."""
        return self.db.query(SalesOrder).filter(
            SalesOrder.business_id == business_id,
            SalesOrder.customer_id == customer_id,
        ).offset(skip).limit(limit).all()

    def create_line_item(self, **kwargs) -> OrderLineItem:
        """Create a line item for an order."""
        line_item = OrderLineItem(**kwargs)
        self.db.add(line_item)
        self.db.commit()
        self.db.refresh(line_item)
        return line_item
