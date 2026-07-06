"""Sales order service - business logic with auto-event emission."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import ALL_BUSINESS_ROLES, PRIVILEGED_ROLES, require_role
from app.models.inventory import InventoryLocation, StockLevel
from app.models.sales_order import SalesOrder
from app.repositories.sales_order import SalesOrderRepository
from app.schemas.sales_order import OrderCreate, OrderUpdate
from app.schemas.auth import CurrentUser


class SalesOrderService:
    """Sales order service with RBAC and state machine."""

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = SalesOrderRepository(db)
        self._event_service = event_service

    def _emit_event(self, event_type: EventType, business_id: UUID, entity_id: UUID, actor_id: UUID | None = None, description: str | None = None, data: dict | None = None) -> None:
        """Queue an event row in the same (not-yet-committed) transaction as
        the caller's pending business-row change - the caller commits once,
        after this call, so both persist atomically or neither does."""
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id, event_type=event_type, entity_type="sales_order",
            entity_id=entity_id, actor_id=actor_id, description=description, data=data,
            commit=False,
        )

    def _get_available_stock(self, business_id: UUID, product_id: UUID) -> int:
        """Return total available units across all active locations for this business."""
        result = (
            self.db.query(func.sum(StockLevel.available))
            .join(InventoryLocation, StockLevel.location_id == InventoryLocation.id)
            .filter(
                StockLevel.product_id == product_id,
                InventoryLocation.business_id == business_id,
                InventoryLocation.is_active.is_(True),
            )
            .scalar()
        )
        return int(result or 0)

    def _reserve_stock(self, business_id: UUID, product_id: UUID, quantity: int) -> None:
        """Increment reserved count across locations (oldest stock first).

        Row-locks the matching StockLevel rows before reading them
        (with_for_update) so two concurrent orders against the same
        low-stock product can't both read the same available count and both
        reserve past it: the second order's transaction blocks until the
        first commits or rolls back, then re-reads the now-current numbers.
        _validate_stock's earlier check is only a fast pre-check for a nicer
        error message - this is the check that's actually race-safe.
        """
        remaining = quantity
        stock_rows = (
            self.db.query(StockLevel)
            .join(InventoryLocation, StockLevel.location_id == InventoryLocation.id)
            .filter(
                StockLevel.product_id == product_id,
                InventoryLocation.business_id == business_id,
                InventoryLocation.is_active.is_(True),
                StockLevel.available > 0,
            )
            .order_by(StockLevel.last_counted_at.asc().nullsfirst())
            .with_for_update()
            .all()
        )
        total_available = sum(int(row.available) for row in stock_rows)
        if total_available < quantity:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Insufficient stock for one or more products",
                    "errors": [
                        f"Product {product_id}: requested {quantity}, "
                        f"only {total_available} available"
                    ],
                },
            )
        for row in stock_rows:
            if remaining <= 0:
                break
            allocate = min(remaining, int(row.available))
            row.reserved += allocate
            remaining -= allocate

    def _release_stock(self, business_id: UUID, product_id: UUID, quantity: int) -> None:
        """Decrement reserved count when an order is cancelled.

        Row-locked for the same reason as _reserve_stock: two concurrent
        cancellations touching the same StockLevel row would otherwise
        lost-update each other's decrement.
        """
        remaining = quantity
        stock_rows = (
            self.db.query(StockLevel)
            .join(InventoryLocation, StockLevel.location_id == InventoryLocation.id)
            .filter(
                StockLevel.product_id == product_id,
                InventoryLocation.business_id == business_id,
                InventoryLocation.is_active.is_(True),
                StockLevel.reserved > 0,
            )
            .order_by(StockLevel.last_counted_at.asc().nullsfirst())
            .with_for_update()
            .all()
        )
        for row in stock_rows:
            if remaining <= 0:
                break
            release = min(remaining, int(row.reserved))
            row.reserved -= release
            remaining -= release

    def _next_order_number(self, business_id: UUID) -> str:
        year = datetime.now(timezone.utc).year
        count = (
            self.db.query(func.count(SalesOrder.id))
            .filter(SalesOrder.business_id == business_id)
            .scalar() or 0
        )
        return f"SO-{year}-{count + 1:05d}"

    def _validate_stock(self, business_id: UUID, data: OrderCreate) -> None:
        """Raise HTTP 400 listing every product that has insufficient stock."""
        errors: list[str] = []
        for item in data.line_items:
            if not item.product_id:
                continue  # Free-text line items are not inventory-managed
            available = self._get_available_stock(business_id, item.product_id)
            if available < item.quantity:
                errors.append(
                    f"Product {item.product_id}: requested {item.quantity}, "
                    f"only {available} available"
                )
        if errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "Insufficient stock for one or more products", "errors": errors},
            )

    def create(self, business_id: UUID, current_user: CurrentUser, data: OrderCreate) -> SalesOrder:
        require_role(current_user, ALL_BUSINESS_ROLES, "create sales orders")

        # Block if any line item exceeds available stock
        self._validate_stock(business_id, data)

        # Create order
        order = self.repo.create(
            business_id=business_id,
            order_number=self._next_order_number(business_id),
            customer_id=data.customer_id,
            lead_id=data.lead_id,
            notes=data.notes,
            internal_notes=data.internal_notes,
            status="draft",
            subtotal=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            shipping_cost=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            commit=False,
        )

        # Create line items and reserve stock
        for item in data.line_items:
            self.repo.create_line_item(order_id=order.id, commit=False, **item.model_dump())
            if item.product_id:
                self._reserve_stock(business_id, item.product_id, item.quantity)

        self._emit_event(
            event_type=EventType.ORDER_CREATED,
            business_id=business_id,
            entity_id=order.id,
            actor_id=current_user.user_id,
            description=f"Sales order {order.order_number} created",
            data={"order_number": order.order_number, "total_amount": float(order.total_amount)}
        )

        self.db.commit()
        self.db.refresh(order)
        return order

    def get(self, business_id: UUID, current_user: CurrentUser, order_id: UUID) -> SalesOrder | None:
        return self.repo.get(business_id=business_id, entity_id=order_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[SalesOrder], int]:
        return self.repo.list(business_id=business_id, skip=skip, limit=limit), self.repo.count(business_id=business_id)

    def update(self, business_id: UUID, current_user: CurrentUser, order_id: UUID, data: OrderUpdate) -> SalesOrder | None:
        require_role(current_user, PRIVILEGED_ROLES, "update sales orders")

        order = self.repo.get(business_id=business_id, entity_id=order_id)
        if not order:
            return None

        old_status = order.status
        updated_order = self.repo.update(business_id=business_id, entity_id=order_id, commit=False, **data.model_dump(exclude_unset=True))

        if updated_order and data.status and data.status != old_status:
            # Determine appropriate event based on status change
            event_type = EventType.ORDER_CREATED # Default fallback
            if data.status == "confirmed":
                event_type = EventType.ORDER_CONFIRMED
            elif data.status == "shipped":
                event_type = EventType.ORDER_SHIPPED
            elif data.status == "delivered":
                event_type = EventType.ORDER_DELIVERED
            elif data.status == "cancelled":
                event_type = EventType.ORDER_CANCELLED

            self._emit_event(
                event_type=event_type,
                business_id=business_id,
                entity_id=order_id,
                actor_id=current_user.user_id,
                description=f"Sales order status changed to {data.status}",
                data={"old_status": old_status, "new_status": data.status}
            )

            if data.status == "cancelled" and old_status != "cancelled":
                for item in order.line_items:
                    if item.product_id:
                        self._release_stock(business_id, item.product_id, item.quantity)

        if updated_order:
            self.db.commit()
            self.db.refresh(updated_order)

        return updated_order
