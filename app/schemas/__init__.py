"""Pydantic schemas package."""

from app.schemas.auth import CurrentUser, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.schemas.event import EventAuditTrailResponse, EventCreate, EventListResponse, EventResponse
from app.schemas.lead import LeadCreate, LeadListResponse, LeadResponse, LeadUpdate
from app.schemas.metrics import (
    MetricsResponse,
    WorkflowActionMetrics,
    WorkflowDefinitionMetrics,
    WorkflowRunMetrics,
)
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowUpdate,
    WorkflowListResponse,
    WorkflowActionCreate,
    WorkflowActionResponse,
    WorkflowDefinitionCreate,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionResponse,
    WorkflowDefinitionUpdate,
    WorkflowRunResponse,
    WorkflowRunListResponse,
)
from app.schemas.product import ProductCreate, ProductListResponse, ProductResponse, ProductUpdate
from app.schemas.inventory import (
    LocationCreate,
    LocationResponse,
    LocationUpdate,
    StockAdjustment,
    StockLevelCreate,
    StockLevelResponse,
    StockLevelUpdate,
)
from app.schemas.supplier import SupplierCreate, SupplierListResponse, SupplierResponse, SupplierUpdate
from app.schemas.sales_order import (
    LineItemCreate,
    LineItemResponse,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderUpdate,
)
from app.schemas.purchase_order import (
    POCreate,
    POLineItemCreate,
    POLineItemResponse,
    POListResponse,
    POResponse,
    POUpdate,
)

__all__ = [
    # Auth
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "CurrentUser",
    "UserResponse",
    # Customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerListResponse",
    # Event
    "EventCreate",
    "EventResponse",
    "EventListResponse",
    "EventAuditTrailResponse",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    # Metrics
    "WorkflowRunMetrics",
    "WorkflowActionMetrics",
    "WorkflowDefinitionMetrics",
    "MetricsResponse",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskListResponse",
    # User
    "UserCreate",
    "UserUpdate",
    "UserListResponse",
    # Workflow
    "WorkflowCreate",
    "WorkflowResponse",
    "WorkflowUpdate",
    "WorkflowListResponse",
    "WorkflowActionCreate",
    "WorkflowActionResponse",
    "WorkflowDefinitionCreate",
    "WorkflowDefinitionUpdate",
    "WorkflowDefinitionResponse",
    "WorkflowDefinitionListResponse",
    "WorkflowRunResponse",
    "WorkflowRunListResponse",
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductListResponse",
    # Inventory
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    "StockLevelCreate",
    "StockLevelUpdate",
    "StockLevelResponse",
    "StockAdjustment",
    # Supplier
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierResponse",
    "SupplierListResponse",
    # Sales Order
    "OrderCreate",
    "OrderUpdate",
    "OrderResponse",
    "OrderListResponse",
    "LineItemCreate",
    "LineItemResponse",
    # Purchase Order
    "POCreate",
    "POUpdate",
    "POResponse",
    "POListResponse",
    "POLineItemCreate",
    "POLineItemResponse",
]
