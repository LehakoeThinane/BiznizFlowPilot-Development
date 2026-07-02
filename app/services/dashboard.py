"""Dashboard KPI aggregation service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.enums import WorkflowRunStatus
from app.models.inventory import StockLevel
from app.models.lead import Lead
from app.models.product import Product
from app.models.sales_order import SalesOrder
from app.models.supplier import Supplier
from app.models.task import Task
from app.models.workflow import WorkflowDefinition, WorkflowRun
from app.schemas.dashboard import (
    DashboardResponse,
    InventoryKPIs,
    LeadKPIs,
    SalesKPIs,
    TaskKPIs,
    WorkflowKPIs,
)

_OPEN_ORDER_STATUSES = ("draft", "confirmed", "processing")
_REVENUE_STATUSES = ("confirmed", "processing", "shipped", "delivered")


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard(self, business_id: UUID) -> DashboardResponse:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)

        return DashboardResponse(
            business_id=business_id,
            sales=self._sales_kpis(business_id, month_start),
            leads=self._lead_kpis(business_id),
            tasks=self._task_kpis(business_id, now, today_start, tomorrow_start),
            inventory=self._inventory_kpis(business_id),
            workflows=self._workflow_kpis(business_id, today_start),
            refreshed_at=now.isoformat(),
        )

    # ── Sales ───────────────────────────────────────────────────────────────

    def _sales_kpis(self, business_id: UUID, month_start: datetime) -> SalesKPIs:
        base = self.db.query(SalesOrder).filter(SalesOrder.business_id == business_id)

        revenue_total = (
            base.filter(SalesOrder.status.in_(_REVENUE_STATUSES))
            .with_entities(sa.func.coalesce(sa.func.sum(SalesOrder.total_amount), 0))
            .scalar()
        )
        revenue_this_month = (
            base.filter(
                SalesOrder.status.in_(_REVENUE_STATUSES),
                SalesOrder.order_date >= month_start,
            )
            .with_entities(sa.func.coalesce(sa.func.sum(SalesOrder.total_amount), 0))
            .scalar()
        )
        open_orders = base.filter(SalesOrder.status.in_(_OPEN_ORDER_STATUSES)).count()
        orders_total = base.count()

        return SalesKPIs(
            revenue_total=Decimal(str(revenue_total)),
            revenue_this_month=Decimal(str(revenue_this_month)),
            open_orders=open_orders,
            orders_total=orders_total,
        )

    # ── Leads ───────────────────────────────────────────────────────────────

    def _lead_kpis(self, business_id: UUID) -> LeadKPIs:
        base = self.db.query(Lead).filter(Lead.business_id == business_id)

        def count_status(s: str) -> int:
            return base.filter(Lead.status == s).count()

        open_leads = base.filter(Lead.status.notin_(("won", "lost"))).count()

        return LeadKPIs(
            open_leads=open_leads,
            new_leads=count_status("new"),
            qualified_leads=count_status("qualified"),
            won_leads=count_status("won"),
            lost_leads=count_status("lost"),
        )

    # ── Tasks ───────────────────────────────────────────────────────────────

    def _task_kpis(
        self,
        business_id: UUID,
        now: datetime,
        today_start: datetime,
        tomorrow_start: datetime,
    ) -> TaskKPIs:
        base = (
            self.db.query(Task)
            .filter(Task.business_id == business_id)
            .filter(Task.status != "completed")
        )

        overdue = base.filter(Task.due_date < now, Task.due_date.isnot(None)).count()
        due_today = base.filter(Task.due_date >= today_start, Task.due_date < tomorrow_start).count()
        pending = base.filter(Task.status == "pending").count()

        return TaskKPIs(overdue=overdue, due_today=due_today, pending=pending)

    # ── Inventory ───────────────────────────────────────────────────────────

    def _inventory_kpis(self, business_id: UUID) -> InventoryKPIs:
        active_products = (
            self.db.query(Product)
            .filter(Product.business_id == business_id, Product.is_active.is_(True))
            .count()
        )
        total_suppliers = (
            self.db.query(Supplier)
            .filter(Supplier.business_id == business_id, Supplier.is_active.is_(True))
            .count()
        )

        # Low stock: tracked products where any stock level is below reorder_point
        low_stock = (
            self.db.query(sa.func.count(sa.func.distinct(StockLevel.product_id)))
            .join(Product, StockLevel.product_id == Product.id)
            .filter(
                Product.business_id == business_id,
                Product.track_inventory.is_(True),
                StockLevel.available < StockLevel.reorder_point,
                StockLevel.available > 0,
            )
            .scalar()
            or 0
        )
        out_of_stock = (
            self.db.query(sa.func.count(sa.func.distinct(StockLevel.product_id)))
            .join(Product, StockLevel.product_id == Product.id)
            .filter(
                Product.business_id == business_id,
                Product.track_inventory.is_(True),
                StockLevel.available <= 0,
            )
            .scalar()
            or 0
        )

        return InventoryKPIs(
            low_stock_products=low_stock,
            out_of_stock_products=out_of_stock,
            total_active_products=active_products,
            total_suppliers=total_suppliers,
        )

    # ── Workflows ───────────────────────────────────────────────────────────

    def _workflow_kpis(self, business_id: UUID, today_start: datetime) -> WorkflowKPIs:
        total_definitions = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.deleted_at.is_(None),
            )
            .count()
        )
        active_runs = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )
        failed_runs_today = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.FAILED,
                WorkflowRun.created_at >= today_start,
            )
            .count()
        )

        return WorkflowKPIs(
            total_definitions=total_definitions,
            active_runs=active_runs,
            failed_runs_today=failed_runs_today,
        )
