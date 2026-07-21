"""Sample-data seeding for freshly-created free-trial businesses.

A brand-new trial business starts with zero data, same as any real signup -
except a completely empty dashboard doesn't show a visitor anything about
what the product does. Since every query in this app is hard-scoped by
business_id (see app/repositories/base.py), seeding a handful of realistic
rows into a fresh business is provably isolated from every other tenant:
this is the same guarantee that already keeps every paying customer's data
walled off from every other one.

Deliberately modest and hardcoded, not exhaustive or randomly generated -
just enough per hub (HR, Sales & CRM, Inventory, Finance, Purchasing, Tasks,
Messages, Meetings, Documents) that a visitor's first login doesn't look
bare. Includes a second "colleague" User (not really loggable-in - a random
unusable password, same trick used for Google-only accounts) purely so
Messages/Meetings have a second participant to look realistic.
"""

import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.document import Document
from app.models.folder import Folder
from app.models.hr import Department, Employee, LeaveRequest, LeaveType, PayrollPeriod, Payslip
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.customer import CustomerRepository
from app.repositories.inventory import InventoryLocationRepository, StockLevelRepository
from app.repositories.lead import LeadRepository
from app.repositories.meeting import MeetingRepository
from app.repositories.messaging import ConversationRepository
from app.repositories.product import ProductRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.sales_order import SalesOrderRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.task import TaskRepository


def seed_sample_data(db: Session, business_id: UUID, owner_user_id: UUID) -> None:
    """Populate a brand-new trial business with representative sample data.

    Purely additive - every row goes through an existing repository's
    create() (or, for models with no dedicated repository, a plain
    BaseRepository instance or a direct db.add()), inheriting business_id
    scoping exactly like the rest of the app. Does not commit - caller
    controls the transaction boundary (see TrialSignupService, which seeds
    this before its own commit so a failure here rolls back the whole
    signup).
    """
    today = date.today()
    now = datetime.now(timezone.utc)

    # ── Colleague account (for Messages/Meetings realism only) ───────────
    # Never actually loggable-in - same random-unusable-password trick used
    # for Google-only accounts - exists purely so the demo has a second
    # participant to message/meet with.
    colleague = User(
        business_id=business_id, email="naledi.khumalo@example-demo.invalid",
        first_name="Naledi", last_name="Khumalo",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role="manager", auth_provider="password", is_active=True,
    )
    db.add(colleague)
    db.flush()

    # ── HR ────────────────────────────────────────────────────────────────
    dept_repo = BaseRepository(db, Department)
    department = dept_repo.create(
        business_id=business_id, commit=False, name="Operations", description="General operations"
    )
    db.flush()

    emp_repo = BaseRepository(db, Employee)
    employee_a = emp_repo.create(
        business_id=business_id, commit=False, department_id=department.id, user_id=colleague.id,
        first_name="Naledi", last_name="Khumalo", position="Operations Manager",
        employment_type="full_time", salary_type="monthly", gross_salary="28000",
        start_date=today - timedelta(days=400), is_active=True,
    )
    employee_b = emp_repo.create(
        business_id=business_id, commit=False, department_id=department.id,
        first_name="Thabo", last_name="Nkosi", position="Sales Representative",
        employment_type="full_time", salary_type="monthly", gross_salary="18500",
        start_date=today - timedelta(days=220), is_active=True,
    )
    employee_c = emp_repo.create(
        business_id=business_id, commit=False, department_id=department.id,
        first_name="Aisha", last_name="Patel", position="Warehouse Assistant",
        employment_type="part_time", salary_type="hourly", gross_salary="120",
        start_date=today - timedelta(days=90), is_active=True,
    )
    db.flush()

    # ── Leave ─────────────────────────────────────────────────────────────
    leave_type_repo = BaseRepository(db, LeaveType)
    annual_leave = leave_type_repo.create(
        business_id=business_id, commit=False, name="Annual Leave", default_days="21", is_paid=True
    )
    sick_leave = leave_type_repo.create(
        business_id=business_id, commit=False, name="Sick Leave", default_days="10", is_paid=True
    )
    db.flush()

    leave_request_repo = BaseRepository(db, LeaveRequest)
    leave_request_repo.create(
        business_id=business_id, commit=False, employee_id=employee_b.id, leave_type_id=annual_leave.id,
        start_date=today + timedelta(days=10), end_date=today + timedelta(days=14),
        days_requested="5", status="pending", reason="Family trip",
    )
    leave_request_repo.create(
        business_id=business_id, commit=False, employee_id=employee_c.id, leave_type_id=sick_leave.id,
        start_date=today - timedelta(days=20), end_date=today - timedelta(days=19),
        days_requested="2", status="approved", reason="Flu",
        approved_by=owner_user_id, approved_at=now - timedelta(days=19),
    )

    # ── Payroll ───────────────────────────────────────────────────────────
    payroll_repo = BaseRepository(db, PayrollPeriod)
    payroll_period = payroll_repo.create(
        business_id=business_id, commit=False, period_year=today.year, period_month=today.month,
        status="completed", total_gross="46620.00", total_deductions="7458.00", total_net="39162.00",
        processed_by=owner_user_id, processed_at=now - timedelta(days=2),
    )
    db.flush()

    payslip_repo = BaseRepository(db, Payslip)
    payslip_repo.create(
        business_id=business_id, commit=False, payroll_period_id=payroll_period.id, employee_id=employee_a.id,
        basic_pay="28000.00", gross_pay="28000.00", tax_deduction="4200.00", uif_deduction="280.00",
        total_deductions="4480.00", net_pay="23520.00", status="finalized",
    )
    payslip_repo.create(
        business_id=business_id, commit=False, payroll_period_id=payroll_period.id, employee_id=employee_b.id,
        basic_pay="18500.00", gross_pay="18500.00", tax_deduction="2775.00", uif_deduction="185.00",
        total_deductions="2960.00", net_pay="15540.00", status="finalized",
    )
    payslip_repo.create(
        business_id=business_id, commit=False, payroll_period_id=payroll_period.id, employee_id=employee_c.id,
        basic_pay="120.00", gross_pay="120.00", tax_deduction="18.00", uif_deduction="1.20",
        total_deductions="19.20", net_pay="100.80", status="finalized",
    )

    # ── Customers (for the Sales/Finance rows below) ─────────────────────
    customer_repo = CustomerRepository(db)
    customer_a = customer_repo.create(
        business_id=business_id, commit=False, name="Karabo Traders",
        email="accounts@karabotraders.example", company="Karabo Traders (Pty) Ltd",
    )
    customer_b = customer_repo.create(
        business_id=business_id, commit=False, name="Sunrise Retail Group",
        email="procurement@sunriseretail.example", company="Sunrise Retail Group",
    )
    db.flush()

    # ── Sales & CRM ───────────────────────────────────────────────────────
    lead_repo = LeadRepository(db)
    lead_repo.create(
        business_id=business_id, commit=False, customer_id=customer_a.id,
        assigned_to=owner_user_id, status="qualified", source="referral", value="45000",
        notes="Interested in a bulk order, follow up next week.",
    )
    lead_repo.create(
        business_id=business_id, commit=False, customer_id=customer_b.id,
        assigned_to=owner_user_id, status="contacted", source="web_form", value="12000",
    )
    lead_repo.create(
        business_id=business_id, commit=False, status="new", source="cold_call", value="8000",
        notes="Left a voicemail, awaiting callback.",
    )
    lead_repo.create(business_id=business_id, commit=False, status="new", source="web_form", value="3000")

    # ── Inventory ─────────────────────────────────────────────────────────
    product_repo = ProductRepository(db)
    product_a = product_repo.create(
        business_id=business_id, commit=False, sku="SKU-1001", name="Steel Bracket (Small)",
        product_type="physical", category="Hardware", unit_price="45.00", cost_price="22.00",
    )
    product_b = product_repo.create(
        business_id=business_id, commit=False, sku="SKU-1002", name="Steel Bracket (Large)",
        product_type="physical", category="Hardware", unit_price="89.00", cost_price="48.00",
    )
    product_repo.create(
        business_id=business_id, commit=False, sku="SKU-1003", name="Packing Tape (48mm)",
        product_type="physical", category="Consumables", unit_price="12.50", cost_price="6.00",
    )
    product_repo.create(
        business_id=business_id, commit=False, sku="SKU-1004", name="Annual Support Plan",
        product_type="service", category="Services", unit_price="4500.00",
    )

    supplier_repo = SupplierRepository(db)
    supplier_a = supplier_repo.create(
        business_id=business_id, commit=False, name="Highveld Steel Supplies", code="SUP-001",
        email="sales@highveldsteel.example", payment_terms="Net 30",
    )
    supplier_repo.create(
        business_id=business_id, commit=False, name="Packrite Consumables", code="SUP-002",
        email="orders@packrite.example", payment_terms="Net 14",
    )
    db.flush()

    location_repo = InventoryLocationRepository(db)
    location = location_repo.create(
        business_id=business_id, commit=False, name="Main Warehouse", location_type="warehouse"
    )
    db.flush()

    stock_repo = StockLevelRepository(db)
    stock_repo.create(
        business_id=business_id, commit=False, product_id=product_a.id, location_id=location.id,
        quantity=150, reorder_point=30, reorder_quantity=100,
    )
    stock_repo.create(
        business_id=business_id, commit=False, product_id=product_b.id, location_id=location.id,
        quantity=60, reorder_point=20, reorder_quantity=50,
    )

    # ── Sales order + Invoice (Finance) ──────────────────────────────────
    sales_order_repo = SalesOrderRepository(db)
    sales_order = sales_order_repo.create(
        business_id=business_id, commit=False, order_number="SO-DEMO-0001",
        customer_id=customer_a.id, status="confirmed", total_amount="1780.00",
        subtotal="1780.00", created_by=owner_user_id,
    )
    db.flush()
    sales_order_repo.create_line_item(
        commit=False, order_id=sales_order.id, product_id=product_a.id,
        quantity=20, unit_price="45.00", subtotal="900.00",
    )
    sales_order_repo.create_line_item(
        commit=False, order_id=sales_order.id, product_id=product_b.id,
        quantity=10, unit_price="88.00", subtotal="880.00",
    )

    invoice_repo = BaseRepository(db, Invoice)
    invoice = invoice_repo.create(
        business_id=business_id, commit=False, invoice_number="INV-DEMO-0001",
        customer_id=customer_a.id, sales_order_id=sales_order.id, status="sent",
        issue_date=today - timedelta(days=5), due_date=today + timedelta(days=25),
        subtotal="1780.00", total_amount="1780.00",
    )
    db.flush()
    # InvoiceLineItem has no business_id column and no dedicated repository -
    # constructed directly and added to the session, same as BaseRepository
    # itself does internally. This is a plain insert, not a raw ORM read.
    db.add(InvoiceLineItem(
        invoice_id=invoice.id, description="Steel Bracket (Small) x20",
        quantity="20", unit_price="45.00", subtotal="900.00",
    ))
    db.add(InvoiceLineItem(
        invoice_id=invoice.id, description="Steel Bracket (Large) x10",
        quantity="10", unit_price="88.00", subtotal="880.00",
    ))

    # ── Purchase order (Purchasing) ──────────────────────────────────────
    po_repo = PurchaseOrderRepository(db)
    purchase_order = po_repo.create(
        business_id=business_id, commit=False, po_number="PO-DEMO-0001",
        supplier_id=supplier_a.id, status="sent", total_cost="1100.00",
        subtotal="1100.00", created_by=owner_user_id,
    )
    db.flush()
    po_repo.create_line_item(
        commit=False, po_id=purchase_order.id, product_id=product_a.id,
        quantity_ordered=50, unit_cost="22.00", subtotal="1100.00",
    )

    # ── Tasks ─────────────────────────────────────────────────────────────
    task_repo = TaskRepository(db)
    task_repo.create(
        business_id=business_id, commit=False, title="Follow up with Karabo Traders",
        status="in_progress", priority="high", assigned_to=owner_user_id,
        due_date=today + timedelta(days=2),
    )
    task_repo.create(
        business_id=business_id, commit=False, title="Reconcile Main Warehouse stock count",
        status="pending", priority="medium", due_date=today + timedelta(days=7),
    )

    # ── Messages ──────────────────────────────────────────────────────────
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.create(business_id=business_id, commit=False)
    db.flush()
    conversation_repo.add_participant(conversation.id, owner_user_id)
    conversation_repo.add_participant(conversation.id, colleague.id)
    conversation_repo.add_message(
        conversation.id, colleague.id, "Welcome aboard! Let me know if you need anything set up."
    )
    conversation_repo.add_message(
        conversation.id, owner_user_id, "Thanks Naledi - just exploring the platform today."
    )
    conversation_repo.add_message(
        conversation.id, colleague.id, "Sounds good - the Karabo Traders order is confirmed and ready to ship."
    )

    # ── Meetings ──────────────────────────────────────────────────────────
    meeting_repo = MeetingRepository(db)
    meeting = meeting_repo.create(
        business_id=business_id, commit=False, organizer_id=owner_user_id,
        title="Weekly operations sync", description="Review open orders and warehouse stock levels.",
        start_time=now + timedelta(days=2, hours=1), end_time=now + timedelta(days=2, hours=1, minutes=30),
        call_type="video", status="scheduled",
        agora_channel_name=f"demo-{business_id.hex[:12]}",
    )
    db.flush()
    meeting_repo.add_participant(meeting.id, colleague.id, response_status="accepted")

    # ── Documents ─────────────────────────────────────────────────────────
    # DB-only rows (no real file uploaded to object storage) - fine for
    # populating list views, but this demo document isn't actually
    # downloadable since no bytes exist in R2 for its storage_key.
    folder_repo = BaseRepository(db, Folder)
    folder = folder_repo.create(
        business_id=business_id, commit=False, name="Company Documents", created_by=owner_user_id
    )
    db.flush()

    document_repo = BaseRepository(db, Document)
    document_repo.create(
        business_id=business_id, commit=False, entity_type="folder", entity_id=folder.id,
        uploaded_by=owner_user_id, filename="Welcome Guide.pdf", content_type="application/pdf",
        size_bytes=24576, storage_key=f"demo/{business_id.hex}/welcome-guide-{uuid4().hex[:8]}.pdf",
    )

    db.flush()
