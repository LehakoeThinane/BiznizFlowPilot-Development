"""Dashboard KPI response schema."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class SalesKPIs(BaseModel):
    revenue_total: Decimal
    revenue_this_month: Decimal
    open_orders: int
    orders_total: int


class LeadKPIs(BaseModel):
    open_leads: int
    new_leads: int
    qualified_leads: int
    won_leads: int
    lost_leads: int


class TaskKPIs(BaseModel):
    overdue: int
    due_today: int
    pending: int


class InventoryKPIs(BaseModel):
    low_stock_products: int
    out_of_stock_products: int
    total_active_products: int
    total_suppliers: int


class WorkflowKPIs(BaseModel):
    total_definitions: int
    active_runs: int
    failed_runs_today: int


class DashboardResponse(BaseModel):
    business_id: UUID
    sales: SalesKPIs
    leads: LeadKPIs
    tasks: TaskKPIs
    inventory: InventoryKPIs
    workflows: WorkflowKPIs
    refreshed_at: str
