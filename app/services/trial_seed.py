"""Sample-data seeding for freshly-created free-trial businesses.

A brand-new trial business starts with zero data, same as any real signup -
except a completely empty dashboard doesn't show a visitor anything about
what the product does. Since every query in this app is hard-scoped by
business_id (see app/repositories/base.py), seeding a large, realistic set
of rows into a fresh business is provably isolated from every other tenant:
this is the same guarantee that already keeps every paying customer's data
walled off from every other one.

Deliberately generated to look like an established, ~75-person company
rather than a 3-person startup - every module (HR, Sales & CRM, Inventory,
Sales Orders, Purchasing, Finance, Tasks, Messages, Meetings, Documents,
Notifications) gets enough rows, across enough statuses, that a visitor's
first login looks like a real business rather than an empty shell.

Only two rows in the whole dataset are actual logins: the trial owner
(passed in) and one "colleague" User (Naledi Khumalo, Operations Manager -
a random-unusable-password account, same trick used for Google-only
accounts) purely so Messages/Meetings/Polls have a second real participant.
Every other person on the org chart is a plain Employee row with no
user_id - real headcount for HR/payroll, but not a login seat.

Not seeded on purpose:
- UserEmailAccount: needs real IMAP/SMTP credentials to actually function;
  a fake row would just show connection errors.
- Event: the workflow dispatcher claims pending Event rows and acts on
  them - seeding fake ones risks real automation side effects.
- Workflow/WorkflowAction: same live-automation risk if left enabled.
- ChatConversation/ChatMessage: that's the AI copilot's own history, not
  general business data.
"""

import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.document import Document
from app.models.finance import Expense, ExpenseCategory
from app.models.hr import Department, Employee, LeaveRequest, LeaveType, PayrollPeriod, Payslip
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.notification import Notification
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.customer import CustomerRepository
from app.repositories.folder import FolderRepository
from app.repositories.inventory import InventoryLocationRepository, StockLevelRepository
from app.repositories.lead import LeadRepository
from app.repositories.meeting import MeetingRepository
from app.repositories.messaging import ConversationRepository
from app.repositories.poll import PollRepository
from app.repositories.product import ProductRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.purchase_requisition import PurchaseRequisitionRepository
from app.repositories.sales_order import SalesOrderRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.task import TaskRepository

# ── Name generation for the employee roster ─────────────────────────────────
# Excludes "Naledi"/"Khumalo" (the one real colleague login) so no generated
# employee can ever collide with that identity.
_FIRST_NAMES = [
    "Thabo", "Zanele", "Kagiso", "Lerato", "Bongani", "Nomvula", "Tumi", "Karabo",
    "Palesa", "Mpho", "Sizwe", "Refilwe", "Andile", "Nosipho", "Katlego", "Ayanda",
    "Zodwa", "Lindiwe", "Mandla", "Precious", "Thandeka", "Sibusiso", "Nokuthula", "Vusi",
]
_LAST_NAMES = [
    "Dlamini", "Mokoena", "Naidoo", "Van der Merwe", "Botha", "Sithole", "Mahlangu", "Zulu",
    "Ngcobo", "Kunene", "Radebe", "Molefe", "Mnguni", "Pillay", "Govender", "Cele",
    "Mabaso", "Sibiya", "Maseko", "Tshabalala", "Fourie", "Reddy", "Mokwena",
]


def _name(i: int) -> tuple[str, str]:
    return _FIRST_NAMES[i % len(_FIRST_NAMES)], _LAST_NAMES[(i * 5 + 3) % len(_LAST_NAMES)]


def _money(value) -> str:
    return str(Decimal(value).quantize(Decimal("0.01")))


# department name, manager title, list of staff position titles (one entry per hire)
_DEPARTMENTS_SPEC: list[tuple[str, str, list[str]]] = [
    ("Operations", "Operations Manager", [
        "Operations Coordinator", "Operations Coordinator", "Operations Coordinator", "Operations Coordinator",
        "Logistics Clerk", "Logistics Clerk", "Facilities Assistant", "Facilities Assistant",
        "Junior Operations Analyst",
    ]),
    ("Sales & CRM", "Sales Manager", [
        "Sales Representative", "Sales Representative", "Sales Representative", "Sales Representative",
        "Sales Representative", "Sales Representative", "Sales Representative", "Sales Representative",
        "Account Manager", "Account Manager", "Account Manager",
        "Sales Administrator", "Sales Administrator", "Sales Administrator",
    ]),
    ("Finance", "Finance Manager", [
        "Accountant", "Accountant", "Bookkeeper", "Bookkeeper",
        "Payroll Administrator", "Accounts Payable Clerk", "Accounts Receivable Clerk",
    ]),
    ("Human Resources", "HR Manager", [
        "HR Officer", "HR Officer", "Recruitment Coordinator", "Payroll & Benefits Administrator",
    ]),
    ("Warehouse & Logistics", "Warehouse Manager", [
        "Warehouse Assistant", "Warehouse Assistant", "Warehouse Assistant",
        "Warehouse Assistant", "Warehouse Assistant", "Warehouse Assistant",
        "Forklift Operator", "Forklift Operator", "Forklift Operator",
        "Delivery Driver", "Delivery Driver", "Delivery Driver",
    ]),
    ("Information Technology", "IT Manager", [
        "IT Support Technician", "IT Support Technician", "Systems Administrator",
        "Junior Developer", "Junior Developer",
    ]),
    ("Marketing", "Marketing Manager", [
        "Marketing Coordinator", "Marketing Coordinator", "Content Specialist",
        "Graphic Designer", "Digital Marketing Analyst", "Social Media Coordinator",
    ]),
    ("Customer Support", "Customer Support Manager", [
        "Support Agent", "Support Agent", "Support Agent", "Support Agent",
        "Support Agent", "Support Agent", "Support Agent",
        "Senior Support Agent", "Senior Support Agent",
    ]),
]
# 8 managers + 66 staff + 1 owner (Executive) = 75 employees total.

# A handful of past employees who've since left, so HR shows real turnover
# history (is_active=False + end_date) instead of everyone still employed.
_INACTIVE_PERSON_INDEXES = {18, 42, 61}

# A few more department managers who (like Naledi/Operations) also get a
# real, non-loginable User account - purely so Messages has more than one
# person to talk to. Every other employee is HR-only headcount with no
# user_id, since Task/Message participants must reference a real User row.
_MESSAGING_COLLEAGUES: dict[str, tuple[str, str]] = {
    "Sales & CRM": ("Karabo", "Sithole"),
    "Finance": ("Lerato", "Mokoena"),
    "Warehouse & Logistics": ("Sizwe", "Ngcobo"),
}

_CUSTOMERS_DATA = [
    ("Karabo Traders", "accounts@karabotraders.example", "Karabo Traders (Pty) Ltd"),
    ("Sunrise Retail Group", "procurement@sunriseretail.example", "Sunrise Retail Group"),
    ("Highveld Manufacturing", "info@highveldmanufacturing.example", "Highveld Manufacturing (Pty) Ltd"),
    ("Coastal Logistics", "ops@coastallogistics.example", "Coastal Logistics CC"),
    ("Ubuntu Office Solutions", "sales@ubuntuoffice.example", "Ubuntu Office Solutions"),
    ("Delta Construction Supplies", "orders@deltaconstruction.example", "Delta Construction Supplies"),
    ("Metro Fashion House", "buying@metrofashion.example", "Metro Fashion House (Pty) Ltd"),
    ("Golden Fields Agri", "procurement@goldenfields.example", "Golden Fields Agricultural Co"),
    ("Silverline Electronics", "purchasing@silverline.example", "Silverline Electronics"),
    ("Baobab Hospitality Group", "supply@baobabhospitality.example", "Baobab Hospitality Group"),
    ("Ekasi Foods", "orders@ekasifoods.example", "Ekasi Foods (Pty) Ltd"),
    ("Northgate Motors", "parts@northgatemotors.example", "Northgate Motors"),
    ("Bright Star Pharmacy Group", "procurement@brightstarpharma.example", "Bright Star Pharmacy Group"),
    ("Riverside Schools Trust", "admin@riversideschools.example", "Riverside Schools Trust"),
    ("Kopano Mining Services", "supply@kopanomining.example", "Kopano Mining Services"),
    ("Fynbos Landscaping", "info@fynboslandscaping.example", "Fynbos Landscaping (Pty) Ltd"),
    ("Zenith Security Group", "accounts@zenithsecurity.example", "Zenith Security Group"),
    ("Harbor View Hotels", "purchasing@harborviewhotels.example", "Harbor View Hotels"),
]

_PRODUCTS_DATA = [
    ("Steel Bracket (Small)", "physical", "Hardware", "45.00", "22.00"),
    ("Steel Bracket (Large)", "physical", "Hardware", "89.00", "48.00"),
    ("Steel Hinge Set", "physical", "Hardware", "65.00", "34.00"),
    ("M8 Bolt (Box of 100)", "physical", "Hardware", "120.00", "70.00"),
    ("M10 Bolt (Box of 100)", "physical", "Hardware", "145.00", "88.00"),
    ("Packing Tape (48mm)", "physical", "Consumables", "12.50", "6.00"),
    ("Bubble Wrap Roll", "physical", "Consumables", "85.00", "42.00"),
    ("Cardboard Box (Medium)", "physical", "Consumables", "8.00", "3.50"),
    ("Cardboard Box (Large)", "physical", "Consumables", "12.00", "5.50"),
    ("Shrink Wrap Roll", "physical", "Consumables", "95.00", "50.00"),
    ("Wireless Barcode Scanner", "physical", "Electronics", "1250.00", "780.00"),
    ("Thermal Label Printer", "physical", "Electronics", "2400.00", "1600.00"),
    ("Handheld Radio", "physical", "Electronics", "890.00", "520.00"),
    ("Tablet POS Stand", "physical", "Electronics", "650.00", "380.00"),
    ("Safety Helmet", "physical", "Safety Equipment", "180.00", "95.00"),
    ("Hi-Vis Safety Vest", "physical", "Safety Equipment", "95.00", "45.00"),
    ("Steel-Toe Safety Boots", "physical", "Safety Equipment", "650.00", "380.00"),
    ("Safety Goggles", "physical", "Safety Equipment", "65.00", "28.00"),
    ("Fire Extinguisher (5kg)", "physical", "Safety Equipment", "450.00", "270.00"),
    ("Pallet Wrap Dispenser", "physical", "Warehouse Equipment", "320.00", "180.00"),
    ("Heavy-Duty Pallet Jack", "physical", "Warehouse Equipment", "4800.00", "3100.00"),
    ("Warehouse Shelving Unit", "physical", "Warehouse Equipment", "1850.00", "1100.00"),
    ("Annual Support Plan", "service", "Services", "4500.00", None),
    ("On-site Installation", "service", "Services", "1800.00", None),
    ("Extended Warranty (2yr)", "service", "Services", "950.00", None),
    ("Staff Training Workshop", "service", "Services", "3200.00", None),
]

_SUPPLIERS_DATA = [
    ("Highveld Steel Supplies", "SUP-001", "sales@highveldsteel.example", "Net 30"),
    ("Packrite Consumables", "SUP-002", "orders@packrite.example", "Net 14"),
    ("TechWorks Distribution", "SUP-003", "sales@techworksdist.example", "Net 30"),
    ("SafetyFirst Supplies", "SUP-004", "orders@safetyfirst.example", "Net 30"),
    ("Warehouse Solutions Co", "SUP-005", "sales@warehousesolutions.example", "Net 45"),
    ("Rapid Print & Label", "SUP-006", "orders@rapidprint.example", "Net 14"),
    ("Metro Hardware Wholesale", "SUP-007", "sales@metrohardware.example", "Net 30"),
    ("National Fastener Supply", "SUP-008", "orders@nationalfastener.example", "Net 30"),
    ("Prime Packaging Group", "SUP-009", "sales@primepackaging.example", "Net 21"),
]

_TASK_TITLE_TEMPLATES = [
    "Follow up with {customer}", "Reconcile {location} stock count", "Prepare monthly payroll run",
    "Review supplier contract renewal", "Update product catalog pricing", "Onboard new warehouse hire",
    "Audit outstanding invoices", "Schedule quarterly stock take", "Renew fire extinguisher certification",
    "Draft marketing campaign brief", "Investigate late delivery from {supplier}", "Prepare board meeting pack",
    "Review employee leave balances", "Update health & safety policy", "Negotiate new supplier pricing",
    "Set up new starter IT equipment", "Process expense reimbursements", "Review overdue customer accounts",
    "Plan warehouse layout optimisation", "Update customer contact details", "Prepare year-end financial summary",
    "Coordinate team building event",
]

_MEETING_TITLES = [
    "Weekly operations sync", "Sales pipeline review", "Warehouse safety walk-through",
    "Q3 budget planning", "New hire onboarding session", "Supplier contract negotiation",
    "Marketing campaign kickoff", "Customer support retrospective",
]
# (status, day_offset from today) - negative offsets are past/completed meetings.
_MEETING_STATUS_OFFSETS = [
    ("completed", -14), ("completed", -7), ("completed", -3),
    ("scheduled", 2), ("scheduled", 5), ("scheduled", 9),
    ("cancelled", 4), ("scheduled", 12),
]

_EXPENSE_CATEGORY_NAMES = [
    "Travel", "Office Supplies", "Utilities", "Marketing", "Professional Services", "Equipment Maintenance",
]
_EXPENSE_VENDORS = [
    "Shell SA", "Makro", "City Power", "Google Ads", "Deloitte", "ACME Maintenance Services",
    "Uber", "Takealot Business", "Vodacom Business", "Bidvest Waltons",
]


def seed_sample_data(db: Session, business_id: UUID, owner_user_id: UUID) -> None:
    """Populate a brand-new trial business with a realistic, large sample dataset.

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

    owner_user = db.get(User, owner_user_id)
    owner_first = owner_user.first_name if owner_user else "Founder"
    owner_last = owner_user.last_name if owner_user else "Owner"

    # ── Colleague account (for Messages/Meetings/Polls realism only) ─────
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

    # ── HR: departments + a ~75-person roster with a manager hierarchy ───
    dept_repo = BaseRepository(db, Department)
    emp_repo = BaseRepository(db, Employee)

    executive_dept = dept_repo.create(
        business_id=business_id, commit=False, name="Executive", description="Leadership and company direction"
    )
    db.flush()

    owner_employee = emp_repo.create(
        business_id=business_id, commit=False, department_id=executive_dept.id, user_id=owner_user_id,
        first_name=owner_first, last_name=owner_last, position="Managing Director",
        email=owner_user.email if owner_user else None, phone="+27 82 555 0000",
        employment_type="full_time", salary_type="monthly", gross_salary="55000.00",
        start_date=today - timedelta(days=900), is_active=True,
    )
    db.flush()

    all_employees: list[Employee] = [owner_employee]
    extra_colleagues: dict[str, User] = {}
    person_index = 0

    for dept_name, manager_position, staff_positions in _DEPARTMENTS_SPEC:
        department = dept_repo.create(
            business_id=business_id, commit=False, name=dept_name, description=f"{dept_name} team"
        )
        db.flush()

        if dept_name == "Operations":
            manager_employee = emp_repo.create(
                business_id=business_id, commit=False, department_id=department.id, user_id=colleague.id,
                manager_id=owner_employee.id, first_name="Naledi", last_name="Khumalo", position=manager_position,
                email=colleague.email, phone="+27 82 555 0001",
                employment_type="full_time", salary_type="monthly", gross_salary="32000.00",
                start_date=today - timedelta(days=400), is_active=True,
            )
        elif dept_name in _MESSAGING_COLLEAGUES:
            first, last = _MESSAGING_COLLEAGUES[dept_name]
            colleague_user = User(
                business_id=business_id, email=f"{first.lower()}.{last.lower()}@example-demo.invalid",
                first_name=first, last_name=last,
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                role="manager", auth_provider="password", is_active=True,
            )
            db.add(colleague_user)
            db.flush()
            extra_colleagues[dept_name] = colleague_user

            manager_employee = emp_repo.create(
                business_id=business_id, commit=False, department_id=department.id, user_id=colleague_user.id,
                manager_id=owner_employee.id, first_name=first, last_name=last, position=manager_position,
                email=colleague_user.email, phone=f"+27 8{2 + person_index % 7} 555 {1000 + person_index:04d}",
                employment_type="full_time", salary_type="monthly",
                gross_salary=_money(34000 + person_index * 900),
                start_date=today - timedelta(days=300 + person_index * 11), is_active=True,
            )
            person_index += 1
        else:
            first, last = _name(person_index)
            manager_employee = emp_repo.create(
                business_id=business_id, commit=False, department_id=department.id, manager_id=owner_employee.id,
                first_name=first, last_name=last, position=manager_position,
                email=f"{first.lower()}.{last.lower().replace(' ', '')}{person_index}@example-team.invalid",
                phone=f"+27 8{2 + person_index % 7} 555 {1000 + person_index:04d}",
                national_id=f"DEMO-{person_index:06d}", tax_number=f"TAX-{person_index:06d}",
                bank_account=f"ACCT-{person_index:08d}",
                employment_type="full_time", salary_type="monthly",
                gross_salary=_money(34000 + person_index * 900),
                start_date=today - timedelta(days=300 + person_index * 11), is_active=True,
            )
            person_index += 1
        db.flush()
        all_employees.append(manager_employee)

        for position in staff_positions:
            first, last = _name(person_index)
            if person_index % 9 == 8:
                employment_type, salary_type = "contractor", "annual"
                gross_salary = _money(380000 + (person_index % 5) * 15000)
            elif person_index % 6 == 5:
                employment_type, salary_type = "part_time", "hourly"
                gross_salary = _money(95 + (person_index % 5) * 8)
            else:
                employment_type, salary_type = "full_time", "monthly"
                gross_salary = _money(11000 + (person_index % 8) * 1100)

            is_active = person_index not in _INACTIVE_PERSON_INDEXES
            staff_employee = emp_repo.create(
                business_id=business_id, commit=False, department_id=department.id, manager_id=manager_employee.id,
                first_name=first, last_name=last, position=position,
                email=f"{first.lower()}.{last.lower().replace(' ', '')}{person_index}@example-team.invalid",
                phone=f"+27 8{2 + person_index % 8} 555 {1000 + person_index:04d}",
                national_id=f"DEMO-{person_index:06d}", tax_number=f"TAX-{person_index:06d}",
                bank_account=f"ACCT-{person_index:08d}",
                employment_type=employment_type, salary_type=salary_type, gross_salary=gross_salary,
                start_date=today - timedelta(days=30 + (person_index * 37) % 900),
                end_date=(today - timedelta(days=(person_index * 13) % 60)) if not is_active else None,
                is_active=is_active,
            )
            all_employees.append(staff_employee)
            person_index += 1
    db.flush()

    # ── Leave ─────────────────────────────────────────────────────────────
    leave_type_repo = BaseRepository(db, LeaveType)
    annual_leave = leave_type_repo.create(business_id=business_id, commit=False, name="Annual Leave", default_days="21", is_paid=True)
    sick_leave = leave_type_repo.create(business_id=business_id, commit=False, name="Sick Leave", default_days="10", is_paid=True)
    family_leave = leave_type_repo.create(business_id=business_id, commit=False, name="Family Responsibility Leave", default_days="3", is_paid=True)
    study_leave = leave_type_repo.create(business_id=business_id, commit=False, name="Study Leave", default_days="5", is_paid=False)
    unpaid_leave = leave_type_repo.create(business_id=business_id, commit=False, name="Unpaid Leave", default_days="0", is_paid=False)
    db.flush()

    leave_types = [annual_leave, sick_leave, family_leave, study_leave, unpaid_leave]
    _leave_span = {
        "Annual Leave": 5, "Sick Leave": 2, "Family Responsibility Leave": 2,
        "Study Leave": 3, "Unpaid Leave": 4,
    }

    leave_request_repo = BaseRepository(db, LeaveRequest)
    leave_statuses_cycle = ["approved", "approved", "pending", "rejected", "cancelled"]
    staff_pool = all_employees[1:]  # everyone except the owner
    for n in range(25):
        employee = staff_pool[(n * 3 + 2) % len(staff_pool)]
        leave_type = leave_types[n % len(leave_types)]
        status = leave_statuses_cycle[n % len(leave_statuses_cycle)]
        span = _leave_span[leave_type.name]

        if status == "approved":
            start = today - timedelta(days=10 + n)
        elif status == "pending":
            start = today + timedelta(days=5 + n)
        else:
            start = today - timedelta(days=20 + n)
        end = start + timedelta(days=span - 1)

        kwargs = dict(
            business_id=business_id, commit=False, employee_id=employee.id, leave_type_id=leave_type.id,
            start_date=start, end_date=end, days_requested=str(span), status=status,
            reason=f"{leave_type.name} request",
        )
        if status == "approved":
            kwargs["approved_by"] = owner_user_id
            kwargs["approved_at"] = now - timedelta(days=9 + n)
        leave_request_repo.create(**kwargs)
    db.flush()

    # ── Payroll: last two completed months (with payslips for every active
    # employee) + the current month still in draft (not yet processed). ──
    payroll_repo = BaseRepository(db, PayrollPeriod)
    payslip_repo = BaseRepository(db, Payslip)
    active_employees = [e for e in all_employees if e.is_active]

    def _month_offset(base: date, months_back: int) -> tuple[int, int]:
        month = base.month - months_back
        year = base.year
        while month <= 0:
            month += 12
            year -= 1
        return year, month

    def _monthly_equivalent(employee: Employee) -> Decimal:
        amount = Decimal(employee.gross_salary)
        return (amount / 12).quantize(Decimal("0.01")) if employee.salary_type == "annual" else amount

    for months_back, status in ((2, "completed"), (1, "completed"), (0, "draft")):
        year, month = _month_offset(today, months_back)
        period = payroll_repo.create(
            business_id=business_id, commit=False, period_year=year, period_month=month, status=status,
            processed_by=owner_user_id if status == "completed" else None,
            processed_at=(now - timedelta(days=months_back * 30 + 2)) if status == "completed" else None,
        )
        db.flush()
        if status != "completed":
            continue

        total_gross = total_deductions = total_net = Decimal("0")
        for i, employee in enumerate(active_employees):
            basic = _monthly_equivalent(employee)
            overtime = Decimal("150.00") if i % 5 == 0 else Decimal("0.00")
            bonus = Decimal("500.00") if i % 10 == 0 else Decimal("0.00")
            gross = basic + overtime + bonus
            tax = (basic * Decimal("0.15")).quantize(Decimal("0.01"))
            uif = (basic * Decimal("0.01")).quantize(Decimal("0.01"))
            other = Decimal("50.00") if i % 7 == 0 else Decimal("0.00")
            deductions = tax + uif + other
            net = gross - deductions

            payslip_repo.create(
                business_id=business_id, commit=False, payroll_period_id=period.id, employee_id=employee.id,
                basic_pay=str(basic), overtime_pay=str(overtime), bonus=str(bonus), gross_pay=str(gross),
                tax_deduction=str(tax), uif_deduction=str(uif), other_deductions=str(other),
                total_deductions=str(deductions), net_pay=str(net), status="finalized",
            )
            total_gross += gross
            total_deductions += deductions
            total_net += net

        period.total_gross = str(total_gross)
        period.total_deductions = str(total_deductions)
        period.total_net = str(total_net)
    db.flush()

    # ── Customers (Sales & CRM) ──────────────────────────────────────────
    customer_repo = CustomerRepository(db)
    customers = []
    for name, email, company in _CUSTOMERS_DATA:
        n = len(customers)
        customers.append(customer_repo.create(
            business_id=business_id, commit=False, name=name, email=email, company=company,
            phone=f"+27 11 {500 + n:03d} {1000 + n * 3:04d}",
            website=f"https://www.{email.split('@')[1]}",
        ))
    db.flush()

    lead_repo = LeadRepository(db)
    lead_statuses = ["new", "contacted", "qualified", "won", "lost"]
    lead_sources = ["referral", "web_form", "cold_call", "trade_show", "social_media", "partner_referral"]
    leads = []
    for n in range(30):
        customer = customers[n % len(customers)] if n % 4 != 3 else None
        kwargs = dict(
            business_id=business_id, commit=False,
            customer_id=customer.id if customer else None,
            assigned_to=owner_user_id if n % 3 != 0 else None,
            status=lead_statuses[n % len(lead_statuses)], source=lead_sources[n % len(lead_sources)],
            value=str(2000 + (n * 733) % 60000),
        )
        if n % 3 == 0:
            kwargs["notes"] = f"Follow up regarding {lead_sources[n % len(lead_sources)].replace('_', ' ')} enquiry."
        leads.append(lead_repo.create(**kwargs))
    db.flush()

    # ── Inventory ─────────────────────────────────────────────────────────
    product_repo = ProductRepository(db)
    products = []
    for n, (name, ptype, category, unit_price, cost_price) in enumerate(_PRODUCTS_DATA, start=1):
        kwargs = dict(
            business_id=business_id, commit=False, sku=f"SKU-{1000 + n}", name=name,
            product_type=ptype, category=category, unit_price=unit_price, tax_rate="15.00",
            track_inventory=(ptype == "physical"),
            description=f"{name} - {category.lower()} item for general operations.",
        )
        if cost_price:
            kwargs["cost_price"] = cost_price
        products.append(product_repo.create(**kwargs))
    db.flush()
    physical_products = [p for p in products if p.product_type != "service"]

    supplier_repo = SupplierRepository(db)
    suppliers = []
    for n, (name, code, email, terms) in enumerate(_SUPPLIERS_DATA, start=1):
        suppliers.append(supplier_repo.create(
            business_id=business_id, commit=False, name=name, code=code, email=email, payment_terms=terms,
            phone=f"+27 11 {400 + n:03d} {2000 + n * 5:04d}",
            website=f"https://www.{email.split('@')[1]}", tax_id=f"VAT-{4000000000 + n}",
            rating=3 + (n % 3), notes="Preferred supplier - reliable lead times." if n % 2 == 0 else None,
        ))
    db.flush()

    location_repo = InventoryLocationRepository(db)
    main_location = location_repo.create(
        business_id=business_id, commit=False, name="Main Warehouse", code="WH-MAIN", location_type="warehouse"
    )
    regional_location = location_repo.create(
        business_id=business_id, commit=False, name="Regional Depot - Durban", code="WH-DBN", location_type="warehouse"
    )
    db.flush()

    stock_repo = StockLevelRepository(db)
    for n, product in enumerate(physical_products):
        stock_repo.create(
            business_id=business_id, commit=False, product_id=product.id, location_id=main_location.id,
            quantity=40 + (n * 17) % 260, reserved=(n % 5) * 3,
            reorder_point=20 + (n % 4) * 10, reorder_quantity=50 + (n % 3) * 25,
            last_counted_at=now - timedelta(days=n % 14), last_counted_by=owner_user_id,
        )
        if n % 2 == 0:
            stock_repo.create(
                business_id=business_id, commit=False, product_id=product.id, location_id=regional_location.id,
                quantity=15 + (n * 11) % 120, reserved=(n % 3),
                reorder_point=10 + (n % 3) * 5, reorder_quantity=25,
            )
    db.flush()

    # ── Sales orders (line items kept for reuse when building invoices) ──
    sales_order_repo = SalesOrderRepository(db)
    so_statuses = ["draft", "confirmed", "processing", "shipped", "delivered", "cancelled"]
    sales_orders = []
    sales_order_lines: list[list[tuple]] = []
    for n in range(18):
        status = so_statuses[n % len(so_statuses)]
        customer = customers[n % len(customers)]
        line_count = 1 + (n % 3)
        chosen = [physical_products[(n + k) % len(physical_products)] for k in range(line_count)]

        subtotal = Decimal("0")
        line_specs = []
        for product in chosen:
            qty = 2 + (n % 8)
            unit_price = Decimal(product.unit_price)
            line_subtotal = (unit_price * qty).quantize(Decimal("0.01"))
            subtotal += line_subtotal
            line_specs.append((product, qty, unit_price, line_subtotal))

        tax_total = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
        shipping_cost = Decimal("0.00") if status == "draft" else Decimal("75.00")
        total_amount = subtotal + tax_total + shipping_cost

        order = sales_order_repo.create(
            business_id=business_id, commit=False, order_number=f"SO-DEMO-{n + 1:04d}",
            customer_id=customer.id, lead_id=(leads[n].id if n < len(leads) and n % 6 == 0 else None),
            status=status, subtotal=str(subtotal), tax_total=str(tax_total), shipping_cost=str(shipping_cost),
            total_amount=str(total_amount), created_by=owner_user_id,
            shipping_address={"line1": "12 Industrial Rd", "city": "Johannesburg", "postal_code": "2001", "country": "South Africa"},
            notes="Standard delivery terms apply." if n % 4 == 0 else None,
            tracking_number=f"TRK{100000 + n}" if status in ("shipped", "delivered") else None,
            carrier="Courier Guy" if status in ("shipped", "delivered") else None,
        )
        db.flush()
        for product, qty, unit_price, line_subtotal in line_specs:
            sales_order_repo.create_line_item(
                commit=False, order_id=order.id, product_id=product.id,
                quantity=qty, unit_price=str(unit_price), subtotal=str(line_subtotal),
            )
        sales_orders.append(order)
        sales_order_lines.append(line_specs)
    db.flush()

    # ── Purchase orders ───────────────────────────────────────────────────
    po_repo = PurchaseOrderRepository(db)
    po_statuses = ["draft", "sent", "confirmed", "partially_received", "received", "cancelled"]
    purchase_orders = []
    for n in range(12):
        status = po_statuses[n % len(po_statuses)]
        supplier = suppliers[n % len(suppliers)]
        line_count = 1 + (n % 2)
        chosen = [physical_products[(n * 2 + k) % len(physical_products)] for k in range(line_count)]

        subtotal = Decimal("0")
        line_specs = []
        for product in chosen:
            qty = 20 + (n % 6) * 10
            unit_cost = Decimal(product.cost_price) if product.cost_price else (Decimal(product.unit_price) * Decimal("0.55")).quantize(Decimal("0.01"))
            line_subtotal = (unit_cost * qty).quantize(Decimal("0.01"))
            subtotal += line_subtotal
            line_specs.append((product, qty, unit_cost, line_subtotal))

        tax_total = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
        total_cost = subtotal + tax_total

        order = po_repo.create(
            business_id=business_id, commit=False, po_number=f"PO-DEMO-{n + 1:04d}",
            supplier_id=supplier.id, status=status, subtotal=str(subtotal), tax_total=str(tax_total),
            total_cost=str(total_cost), created_by=owner_user_id, receiving_location_id=main_location.id,
            expected_date=(today + timedelta(days=7 + n)) if status not in ("received", "cancelled") else None,
            received_date=(today - timedelta(days=n)) if status == "received" else None,
            notes=f"Restock order with {supplier.name}." if n % 3 == 0 else None,
        )
        db.flush()
        for product, qty, unit_cost, line_subtotal in line_specs:
            po_repo.create_line_item(
                commit=False, po_id=order.id, product_id=product.id,
                quantity_ordered=qty, quantity_received=(qty if status == "received" else 0),
                unit_cost=str(unit_cost), subtotal=str(line_subtotal),
            )
        purchase_orders.append(order)
    db.flush()

    # ── Purchase requisitions (pre-approval requests, distinct from POs) ─
    pr_repo = PurchaseRequisitionRepository(db)
    pr_statuses = ["pending", "pending", "approved", "approved", "rejected", "converted"]
    for n, status in enumerate(pr_statuses):
        supplier = suppliers[n % len(suppliers)]
        product = physical_products[n % len(physical_products)]
        qty = 10 + n * 5
        est_unit_cost = Decimal(product.cost_price) if product.cost_price else Decimal("50.00")
        estimated_total = (est_unit_cost * qty).quantize(Decimal("0.01"))

        kwargs = dict(
            business_id=business_id, commit=False,
            requested_by=(owner_user_id if n % 2 == 0 else colleague.id),
            supplier_id=supplier.id, title=f"Restock request: {product.name}",
            justification="Stock running low ahead of upcoming orders.",
            estimated_total=str(estimated_total), status=status,
        )
        if status in ("approved", "converted"):
            kwargs["approved_by"] = owner_user_id
            kwargs["approved_at"] = now - timedelta(days=5 + n)
        if status == "rejected":
            kwargs["rejection_reason"] = "Budget constraints this quarter."
        if status == "converted":
            kwargs["converted_purchase_order_id"] = purchase_orders[0].id
        requisition = pr_repo.create(**kwargs)
        db.flush()
        pr_repo.create_line_item(
            commit=False, requisition_id=requisition.id, product_id=product.id,
            description=product.name, quantity=qty, estimated_unit_cost=str(est_unit_cost),
        )
    db.flush()

    # ── Invoices (one per sales order, mirroring its line items) ─────────
    invoice_repo = BaseRepository(db, Invoice)
    invoice_statuses = ["draft", "sent", "paid", "overdue", "cancelled", "void"]
    invoices = []
    for n, order in enumerate(sales_orders):
        status = invoice_statuses[n % len(invoice_statuses)]
        subtotal = Decimal(order.subtotal)
        tax_amount = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
        total_amount = subtotal + tax_amount
        issue_date = today - timedelta(days=max(30 - n, n))
        due_date = issue_date + timedelta(days=30)

        kwargs = dict(
            business_id=business_id, commit=False, invoice_number=f"INV-DEMO-{n + 1:04d}",
            customer_id=order.customer_id, sales_order_id=order.id, status=status,
            issue_date=issue_date, due_date=due_date, payment_terms="Net 30",
            subtotal=str(subtotal), tax_amount=str(tax_amount), total_amount=str(total_amount),
        )
        if status == "paid":
            kwargs["paid_at"] = issue_date + timedelta(days=12)
            kwargs["sent_at"] = now - timedelta(days=max(30 - n, n))
        elif status in ("sent", "overdue"):
            kwargs["sent_at"] = now - timedelta(days=max(30 - n, n))
        invoice = invoice_repo.create(**kwargs)
        db.flush()
        for product, qty, unit_price, line_subtotal in sales_order_lines[n]:
            db.add(InvoiceLineItem(
                invoice_id=invoice.id, description=f"{product.name} x{qty}",
                quantity=str(qty), unit_price=str(unit_price), tax_rate="15.00", subtotal=str(line_subtotal),
            ))
        invoices.append(invoice)
    db.flush()

    # ── Expenses ──────────────────────────────────────────────────────────
    expense_cat_repo = BaseRepository(db, ExpenseCategory)
    expense_categories = [
        expense_cat_repo.create(business_id=business_id, commit=False, name=name, description=f"{name} related expenses")
        for name in _EXPENSE_CATEGORY_NAMES
    ]
    db.flush()

    expense_repo = BaseRepository(db, Expense)
    for n in range(24):
        category = expense_categories[n % len(expense_categories)]
        vendor = _EXPENSE_VENDORS[n % len(_EXPENSE_VENDORS)]
        amount = _money(150 + (n * 233) % 4500)
        expense_repo.create(
            business_id=business_id, commit=False, category_id=category.id,
            date=today - timedelta(days=n * 3 + 1), amount=amount,
            description=f"{category.name} expense - {vendor}", vendor=vendor,
            reference=f"EXP-{2000 + n}", paid_by=(owner_user_id if n % 2 == 0 else colleague.id),
            notes="Recurring monthly expense." if n % 5 == 0 else None,
        )
    db.flush()

    # ── Tasks ─────────────────────────────────────────────────────────────
    task_repo = TaskRepository(db)
    task_statuses = ["pending", "in_progress", "completed", "overdue"]
    task_priorities = ["low", "medium", "high", "urgent"]
    tasks = []
    for n, title_template in enumerate(_TASK_TITLE_TEMPLATES):
        title = title_template.format(
            customer=customers[n % len(customers)].name,
            location=main_location.name,
            supplier=suppliers[n % len(suppliers)].name,
        )
        status = task_statuses[n % len(task_statuses)]
        kwargs = dict(
            business_id=business_id, commit=False, title=title,
            status=status, priority=task_priorities[(n * 3) % len(task_priorities)],
            assigned_to=(owner_user_id if n % 2 == 0 else colleague.id),
            due_date=now + timedelta(days=(n % 10) - 3),
            description=f"{title} - flagged during weekly ops review." if n % 4 == 0 else None,
            lead_id=(leads[n % len(leads)].id if n % 5 == 0 else None),
        )
        if status == "completed":
            kwargs["completed_at"] = now - timedelta(days=n % 5)
        task = task_repo.create(**kwargs)
        if n % 6 == 0:
            task_repo.set_assignees(task.id, [owner_user_id, colleague.id], commit=False)
        tasks.append(task)
    db.flush()

    # ── Messages ──────────────────────────────────────────────────────────
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.create(business_id=business_id, commit=False)
    db.flush()
    conversation_repo.add_participant(conversation.id, owner_user_id)
    conversation_repo.add_participant(conversation.id, colleague.id)
    conversation_repo.add_message(conversation.id, colleague.id, "Welcome aboard! Let me know if you need anything set up.")
    conversation_repo.add_message(conversation.id, owner_user_id, "Thanks Naledi - just exploring the platform today.")
    conversation_repo.add_message(conversation.id, colleague.id, "Sounds good - the Karabo Traders order is confirmed and ready to ship.")
    conversation_repo.add_message(conversation.id, colleague.id, "By the way, I've added a poll below for the team lunch next month - vote when you get a chance.")
    conversation_repo.add_message(conversation.id, owner_user_id, "Will do! Things are looking good on the sales side this month.")
    conversation_repo.add_message(conversation.id, colleague.id, "Great to hear - I'll give the warehouse team an update on the new stock arriving Friday.")
    db.flush()

    poll_repo = PollRepository(db)
    poll = poll_repo.create(
        business_id=business_id, commit=False, conversation_id=conversation.id,
        created_by=colleague.id, question="Where should we go for the team lunch?",
    )
    db.flush()
    option_a = poll_repo.add_option(poll.id, "Local restaurant", 0)
    option_b = poll_repo.add_option(poll.id, "Order in at the office", 1)
    poll_repo.add_option(poll.id, "Food truck event", 2)
    db.flush()
    poll_repo.add_vote(poll.id, option_a.id, owner_user_id)
    poll_repo.add_vote(poll.id, option_b.id, colleague.id)

    # One more 1:1 conversation per extra colleague, each on topics relevant
    # to their department, plus a small-group thread with all of them - so
    # Messages looks like an active company, not a single back-and-forth.
    sales_mgr = extra_colleagues.get("Sales & CRM")
    finance_mgr = extra_colleagues.get("Finance")
    warehouse_mgr = extra_colleagues.get("Warehouse & Logistics")

    if sales_mgr:
        convo = conversation_repo.create(business_id=business_id, commit=False)
        db.flush()
        conversation_repo.add_participant(convo.id, owner_user_id)
        conversation_repo.add_participant(convo.id, sales_mgr.id)
        conversation_repo.add_message(convo.id, sales_mgr.id, "Morning! Just wrapped up the call with Harbor View Hotels - they're keen to move forward.")
        conversation_repo.add_message(convo.id, owner_user_id, "That's great news. What's the expected close date?")
        conversation_repo.add_message(convo.id, sales_mgr.id, "Aiming for end of month - I'll draft the sales order once they confirm the PO.")
        conversation_repo.add_message(convo.id, sales_mgr.id, "Also heads up, Zenith Security Group has gone quiet - might need a follow-up call this week.")
        conversation_repo.add_message(convo.id, owner_user_id, "Good catch, I'll add that to my task list.")

    if finance_mgr:
        convo = conversation_repo.create(business_id=business_id, commit=False)
        db.flush()
        conversation_repo.add_participant(convo.id, owner_user_id)
        conversation_repo.add_participant(convo.id, finance_mgr.id)
        conversation_repo.add_message(convo.id, finance_mgr.id, "Hi - just finalized this month's payroll run, everything's balanced.")
        conversation_repo.add_message(convo.id, owner_user_id, "Perfect, thanks for turning that around so quickly.")
        conversation_repo.add_message(convo.id, finance_mgr.id, "No problem. A few invoices are creeping toward overdue too - sending reminders today.")
        conversation_repo.add_message(convo.id, finance_mgr.id, "On the plus side, expenses are tracking under budget for the quarter so far.")
        conversation_repo.add_message(convo.id, owner_user_id, "Great to hear - keep me posted.")

    if warehouse_mgr:
        convo = conversation_repo.create(business_id=business_id, commit=False)
        db.flush()
        conversation_repo.add_participant(convo.id, owner_user_id)
        conversation_repo.add_participant(convo.id, warehouse_mgr.id)
        conversation_repo.add_message(convo.id, warehouse_mgr.id, "Stock count at the Durban depot is done - a couple of SKUs are below reorder point.")
        conversation_repo.add_message(convo.id, owner_user_id, "Which ones should we prioritize on the next purchase order?")
        conversation_repo.add_message(convo.id, warehouse_mgr.id, "Steel brackets and safety goggles mainly - I've already logged a requisition for review.")
        conversation_repo.add_message(convo.id, warehouse_mgr.id, "Also, the new pallet jack arrived - already making a difference on the floor.")
        conversation_repo.add_message(convo.id, owner_user_id, "Nice, glad that's paying off.")

    group_members = [colleague] + [c for c in (sales_mgr, finance_mgr, warehouse_mgr) if c]
    if len(group_members) > 1:
        group = conversation_repo.create(business_id=business_id, commit=False)
        db.flush()
        conversation_repo.add_participant(group.id, owner_user_id)
        for member in group_members:
            conversation_repo.add_participant(group.id, member.id)
        conversation_repo.add_message(group.id, colleague.id, "Quick one for the group - can everyone send me their department's priorities for next week by Friday?")
        if sales_mgr:
            conversation_repo.add_message(group.id, sales_mgr.id, "Sales priorities coming your way - mostly closing the Harbor View deal.")
        if finance_mgr:
            conversation_repo.add_message(group.id, finance_mgr.id, "Finance will have the Q3 numbers ready for review.")
        if warehouse_mgr:
            conversation_repo.add_message(group.id, warehouse_mgr.id, "Warehouse is focused on the stock take and the new supplier onboarding.")
        conversation_repo.add_message(group.id, owner_user_id, "Thanks all - appreciate the updates, let's regroup Monday.")

    db.flush()

    # ── Meetings ──────────────────────────────────────────────────────────
    meeting_repo = MeetingRepository(db)
    for n, (status, day_offset) in enumerate(_MEETING_STATUS_OFFSETS):
        title = _MEETING_TITLES[n]
        start = now + timedelta(days=day_offset, hours=1)
        meeting = meeting_repo.create(
            business_id=business_id, commit=False, organizer_id=owner_user_id,
            title=title, description=f"{title} - review progress and next steps.",
            start_time=start, end_time=start + timedelta(minutes=30),
            call_type="voice" if n % 3 == 0 else "video", status=status,
            agora_channel_name=f"demo-{business_id.hex[:10]}-{n}",
        )
        db.flush()
        response_status = "declined" if n == 3 else ("pending" if n == 5 else "accepted")
        meeting_repo.add_participant(meeting.id, colleague.id, response_status=response_status)
    db.flush()

    # ── Documents ─────────────────────────────────────────────────────────
    # DB-only rows (no real file uploaded to object storage) - fine for
    # populating list views, but these demo documents aren't actually
    # downloadable since no bytes exist in R2 for their storage_keys.
    folder_repo = FolderRepository(db)
    company_folder = folder_repo.create(business_id=business_id, commit=False, name="Company Documents", created_by=owner_user_id)
    db.flush()
    hr_folder = folder_repo.create(business_id=business_id, commit=False, name="HR Policies", created_by=owner_user_id, parent_folder_id=company_folder.id)
    contracts_folder = folder_repo.create(business_id=business_id, commit=False, name="Contracts", created_by=owner_user_id, parent_folder_id=company_folder.id)
    finance_folder = folder_repo.create(business_id=business_id, commit=False, name="Financial Reports", created_by=owner_user_id, parent_folder_id=company_folder.id)
    catalog_folder = folder_repo.create(business_id=business_id, commit=False, name="Product Catalogs", created_by=owner_user_id)
    db.flush()

    document_repo = BaseRepository(db, Document)
    folder_documents = [
        (company_folder.id, "Welcome Guide.pdf", "application/pdf", 24576),
        (hr_folder.id, "Employee Handbook.pdf", "application/pdf", 184320),
        (hr_folder.id, "Leave Policy.pdf", "application/pdf", 51200),
        (hr_folder.id, "Code of Conduct.pdf", "application/pdf", 61440),
        (contracts_folder.id, "Highveld Steel Supplies Agreement.pdf", "application/pdf", 92160),
        (contracts_folder.id, "Packrite Consumables Agreement.pdf", "application/pdf", 88064),
        (contracts_folder.id, "Office Lease Agreement.pdf", "application/pdf", 133120),
        (finance_folder.id, "Q1 Financial Report.xlsx", "application/vnd.ms-excel", 45056),
        (finance_folder.id, "Q2 Financial Report.xlsx", "application/vnd.ms-excel", 46080),
        (finance_folder.id, "Annual Budget.xlsx", "application/vnd.ms-excel", 39936),
        (catalog_folder.id, "2026 Product Catalog.pdf", "application/pdf", 2145728),
        (catalog_folder.id, "Price List.xlsx", "application/vnd.ms-excel", 28672),
    ]
    for folder_id, filename, content_type, size in folder_documents:
        document_repo.create(
            business_id=business_id, commit=False, entity_type="folder", entity_id=folder_id,
            uploaded_by=owner_user_id, filename=filename, content_type=content_type,
            size_bytes=size, storage_key=f"demo/{business_id.hex}/{uuid4().hex[:8]}-{filename}",
        )

    # A few documents attached directly to real records (lead/task/customer/
    # invoice) rather than a folder, so those detail pages show attachments too.
    entity_documents = [
        ("lead", leads[0].id, "Proposal.pdf", "application/pdf", 71680),
        ("lead", leads[2].id, "Meeting Notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 20480),
        ("customer", customers[0].id, "Signed MSA.pdf", "application/pdf", 102400),
        ("customer", customers[1].id, "Credit Application.pdf", "application/pdf", 65536),
        ("invoice", invoices[0].id, "Invoice Backup.pdf", "application/pdf", 30720),
        ("task", tasks[0].id, "Reference Attachment.pdf", "application/pdf", 15360),
    ]
    for entity_type, entity_id, filename, content_type, size in entity_documents:
        document_repo.create(
            business_id=business_id, commit=False, entity_type=entity_type, entity_id=entity_id,
            uploaded_by=owner_user_id, filename=filename, content_type=content_type,
            size_bytes=size, storage_key=f"demo/{business_id.hex}/{uuid4().hex[:8]}-{filename}",
        )
    db.flush()

    # ── Notifications ─────────────────────────────────────────────────────
    notification_repo = BaseRepository(db, Notification)
    low_stock_product = physical_products[0]
    overdue_task = next((t for t in tasks if t.status == "overdue"), tasks[0])
    notifications_data = [
        ("low_stock", f"Low stock: {low_stock_product.name}", f"{low_stock_product.name} has dropped below its reorder point at {main_location.name}.", True),
        ("overdue_task", f"Task overdue: {overdue_task.title}", "This task passed its due date and needs attention.", False),
        ("order_status", f"Order {sales_orders[3].order_number} shipped", "The customer's order has left the warehouse.", True),
        ("order_status", f"Order {sales_orders[5].order_number} delivered", "Delivery confirmed by the courier.", True),
        ("payroll", "Payroll processed", "This month's payroll run has been finalized.", True),
        ("payroll", "Payroll due for review", "Next payroll period is still in draft and needs review before processing.", False),
        ("leave", "New leave request", "A team member has submitted a new leave request awaiting approval.", False),
        ("leave", "Leave request approved", "A pending leave request has been approved.", True),
        ("meeting", f"Upcoming meeting: {_MEETING_TITLES[3]}", "You have a meeting scheduled soon.", False),
        ("meeting", "Meeting cancelled", "A scheduled meeting was cancelled.", True),
        ("system", "Welcome to BiznizFlowPilot", "Your workspace is ready - explore the sidebar to see every module.", True),
        ("system", "New feature: Email inbox", "You can now connect your own mailbox from the Email tab.", False),
        ("low_stock", f"Low stock: {physical_products[4].name}", f"{physical_products[4].name} is running low across all locations.", False),
        ("order_status", f"Purchase order {purchase_orders[1].po_number} received", "Stock has been received into the warehouse.", True),
        ("system", "Trial reminder", "Your free trial is active - upgrade any time to keep every feature.", False),
    ]
    for ntype, title, message, is_read in notifications_data:
        notification_repo.create(
            business_id=business_id, commit=False, user_id=owner_user_id, type=ntype,
            title=title, message=message, is_read=is_read,
        )

    db.flush()
