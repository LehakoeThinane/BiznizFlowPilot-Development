"""Database models package initialization."""

# Import Base from base module
from app.models.base import Base

# Import all models to register them with Base
from app.models.organization import Organization
from app.models.organization_domain import OrganizationDomain
from app.models.business import Business
from app.models.user import User
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.task import Task
from app.models.event import Event
from app.models.workflow import Workflow, WorkflowAction, WorkflowDefinition, WorkflowRun
from app.models.product import Product
from app.models.inventory import InventoryLocation, StockLevel
from app.models.supplier import Supplier
from app.models.sales_order import SalesOrder, OrderLineItem
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLineItem
from app.models.finance import Expense, ExpenseCategory
from app.models.hr import Department, Employee, LeaveRequest, LeaveType, PayrollPeriod, Payslip
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.notification import Notification
from app.models.chat import ChatConversation, ChatMessage
from app.models.user_invitation import UserInvitation
from app.models.platform_admin import PlatformAdmin
from app.models.platform_audit_log import PlatformAuditLog

__all__ = [
    "Base",
    "Organization",
    "OrganizationDomain",
    "Business",
    "User",
    "Customer",
    "Lead",
    "Task",
    "Event",
    "Workflow",
    "WorkflowAction",
    "WorkflowDefinition",
    "WorkflowRun",
    "Product",
    "InventoryLocation",
    "StockLevel",
    "Supplier",
    "SalesOrder",
    "OrderLineItem",
    "PurchaseOrder",
    "PurchaseOrderLineItem",
    "ExpenseCategory",
    "Expense",
    "Department",
    "Employee",
    "LeaveType",
    "LeaveRequest",
    "PayrollPeriod",
    "Payslip",
    "Invoice",
    "InvoiceLineItem",
    "Notification",
    "ChatConversation",
    "ChatMessage",
    "UserInvitation",
    "PlatformAdmin",
    "PlatformAuditLog",
]
