"""API package."""

from app.api import (
    auth,
    chat,
    customers,
    dashboard,
    events,
    inventory,
    leads,
    metrics,
    products,
    purchase_orders,
    sales_orders,
    suppliers,
    tasks,
    users,
    workflow_definitions,
    workflows,
)

__all__ = [
    "auth",
    "chat",
    "customers",
    "dashboard",
    "events",
    "inventory",
    "leads",
    "metrics",
    "products",
    "purchase_orders",
    "sales_orders",
    "suppliers",
    "tasks",
    "users",
    "workflow_definitions",
    "workflows",
]
