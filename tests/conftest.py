"""Pytest configuration and fixtures."""

import os
os.environ["RATELIMIT_ENABLED"] = "False"

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.models.customer import Customer
from app.models.inventory import InventoryLocation
from app.models.lead import Lead
from app.models.platform_admin import PlatformAdmin
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.task import Task
from app.schemas.auth import CurrentUser


@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # Override dependency
    def override_get_db():
        try:
            yield session
        finally:
            session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    # Cleanup
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture
def client(test_db):
    """Create test client with in-memory database."""
    return TestClient(app)


@pytest.fixture
def sample_user_data():
    """Sample user registration data."""
    return {
        "business_name": "Test Company",
        "email": "owner@example.com",
        "password": "testpassword123",
        "first_name": "John",
        "last_name": "Doe",
    }


@pytest.fixture
def registered_user(test_db: Session, sample_user_data):
    """Create an organization/business/owner directly and return tokens for it.

    There is no public self-service registration endpoint (new client
    organizations are provisioned by a platform admin, then the owner
    accepts an invite) - this fixture recreates just the end state
    (a real owner user with valid tokens) that tests need for setup.
    """
    from app.services.auth import AuthService

    organization = Organization(
        id=uuid4(), name=sample_user_data["business_name"], billing_email=sample_user_data["email"],
    )
    test_db.add(organization)
    test_db.commit()

    business = Business(
        id=uuid4(), organization_id=organization.id, name=sample_user_data["business_name"],
        email=sample_user_data["email"], is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()

    user = User(
        id=uuid4(), business_id=business.id, email=sample_user_data["email"],
        hashed_password=hash_password(sample_user_data["password"]),
        first_name=sample_user_data["first_name"], last_name=sample_user_data["last_name"],
        role="owner", is_active=True,
    )
    test_db.add(user)
    test_db.commit()

    tokens = AuthService(test_db)._create_tokens(
        user_id=user.id,
        business_id=business.id,
        email=user.email,
        role="owner",
        full_name=f"{user.first_name} {user.last_name}",
        phash=user.hashed_password[-8:],
    )
    return tokens.model_dump()


# ============================================================================
# Phase 2 Fixtures: Multi-role users and sample CRM data
# ============================================================================


@pytest.fixture
def owner_organization(test_db: Session) -> Organization:
    """Create an organization for owner_business."""
    organization = Organization(
        id=uuid4(),
        name="Owner Organization",
        billing_email=f"owner-org@{uuid4().hex[:8]}.com",
    )
    test_db.add(organization)
    test_db.commit()
    return organization


@pytest.fixture
def other_organization(test_db: Session) -> Organization:
    """Create another organization for isolation testing."""
    organization = Organization(
        id=uuid4(),
        name="Other Organization",
        billing_email=f"other-org@{uuid4().hex[:8]}.com",
    )
    test_db.add(organization)
    test_db.commit()
    return organization


@pytest.fixture
def owner_business(test_db: Session, owner_organization: Organization) -> Business:
    """Create a business for owner."""
    business = Business(
        id=uuid4(),
        organization_id=owner_organization.id,
        name="Owner Business",
        email=f"owner@{uuid4().hex[:8]}.com",
        phone="+1234567890",
        is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()
    return business


@pytest.fixture
def other_business(test_db: Session, other_organization: Organization) -> Business:
    """Create another business for isolation testing."""
    business = Business(
        id=uuid4(),
        organization_id=other_organization.id,
        name="Other Business",
        email=f"other@{uuid4().hex[:8]}.com",
        phone="+0987654321",
        is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()
    return business


@pytest.fixture
def owner_user(test_db: Session, owner_business: Business) -> CurrentUser:
    """Create owner user with access."""
    user = User(
        id=uuid4(),
        business_id=owner_business.id,
        email="owner@test.com",
        hashed_password=hash_password("password123"),
        first_name="Owner",
        last_name="User",
        role="owner",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    
    return CurrentUser(
        user_id=str(user.id),
        business_id=str(owner_business.id),
        email=user.email,
        role="owner",
        full_name=f"{user.first_name} {user.last_name}",
    )


@pytest.fixture
def manager_user(test_db: Session, owner_business: Business) -> CurrentUser:
    """Create manager user with access."""
    user = User(
        id=uuid4(),
        business_id=owner_business.id,
        email="manager@test.com",
        hashed_password=hash_password("password123"),
        first_name="Manager",
        last_name="User",
        role="manager",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    
    return CurrentUser(
        user_id=str(user.id),
        business_id=str(owner_business.id),
        email=user.email,
        role="manager",
        full_name=f"{user.first_name} {user.last_name}",
    )


@pytest.fixture
def staff_user(test_db: Session, owner_business: Business) -> CurrentUser:
    """Create staff user with limited access."""
    user = User(
        id=uuid4(),
        business_id=owner_business.id,
        email="staff@test.com",
        hashed_password=hash_password("password123"),
        first_name="Staff",
        last_name="User",
        role="staff",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    
    return CurrentUser(
        user_id=str(user.id),
        business_id=str(owner_business.id),
        email=user.email,
        role="staff",
        full_name=f"{user.first_name} {user.last_name}",
    )


@pytest.fixture
def org_admin_user(test_db: Session, owner_business: Business) -> CurrentUser:
    """Create IT Admin user, scoped to owner_business's organization."""
    user = User(
        id=uuid4(),
        business_id=owner_business.id,
        email="itadmin@test.com",
        hashed_password=hash_password("password123"),
        first_name="IT",
        last_name="Admin",
        role="it_admin",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()

    return CurrentUser(
        user_id=str(user.id),
        business_id=str(owner_business.id),
        email=user.email,
        role="it_admin",
        full_name=f"{user.first_name} {user.last_name}",
    )


@pytest.fixture
def owner_second_business(test_db: Session, owner_organization: Organization) -> Business:
    """A second, non-primary subsidiary Business in owner_organization."""
    business = Business(
        id=uuid4(),
        organization_id=owner_organization.id,
        name="Owner Subsidiary Two",
        email=f"sub2@{uuid4().hex[:8]}.com",
        phone="+1112223333",
        is_primary_subsidiary=False,
    )
    test_db.add(business)
    test_db.commit()
    return business


@pytest.fixture
def other_user(test_db: Session, other_business: Business) -> CurrentUser:
    """Create user in different business for isolation testing."""
    user = User(
        id=uuid4(),
        business_id=other_business.id,
        email="other@test.com",
        hashed_password=hash_password("password123"),
        first_name="Other",
        last_name="User",
        role="owner",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    
    return CurrentUser(
        user_id=str(user.id),
        business_id=str(other_business.id),
        email=user.email,
        role="owner",
        full_name=f"{user.first_name} {user.last_name}",
    )


@pytest.fixture
def sample_customer(test_db: Session, owner_business: Business) -> Customer:
    """Create sample customer."""
    customer = Customer(
        id=uuid4(),
        business_id=owner_business.id,
        name="Acme Corp",
        email="contact@acme.com",
        phone="+1234567890",
        company="Acme Corporation",
    )
    test_db.add(customer)
    test_db.commit()
    return customer


@pytest.fixture
def sample_lead(test_db: Session, owner_business: Business, sample_customer: Customer) -> Lead:
    """Create sample lead."""
    lead = Lead(
        id=uuid4(),
        business_id=owner_business.id,
        customer_id=sample_customer.id,
        status="new",
        source="web_form",
    )
    test_db.add(lead)
    test_db.commit()
    return lead


@pytest.fixture
def sample_task(test_db: Session, owner_business: Business, sample_lead: Lead) -> Task:
    """Create sample task."""
    task = Task(
        id=uuid4(),
        business_id=owner_business.id,
        lead_id=sample_lead.id,
        title="Follow up with customer",
        description="Call to discuss proposal",
        status="pending",
        priority="high",
    )
    test_db.add(task)
    test_db.commit()
    return task


# ============================================================================
# Platform (vendor staff) Fixtures
# ============================================================================


@pytest.fixture
def platform_admin(test_db: Session) -> PlatformAdmin:
    """Create a platform admin with the default 'support' role."""
    admin = PlatformAdmin(
        id=uuid4(),
        email=f"support-{uuid4().hex[:8]}@vendor.example.com",
        hashed_password=hash_password("password123"),
        full_name="Support Admin",
        platform_role="support",
        is_active=True,
        impersonation_allowed=False,
    )
    test_db.add(admin)
    test_db.commit()
    return admin


@pytest.fixture
def platform_super_admin(test_db: Session) -> PlatformAdmin:
    """Create a platform admin with the 'super_admin' role."""
    admin = PlatformAdmin(
        id=uuid4(),
        email=f"super-{uuid4().hex[:8]}@vendor.example.com",
        hashed_password=hash_password("password123"),
        full_name="Super Admin",
        platform_role="super_admin",
        is_active=True,
        impersonation_allowed=True,
    )
    test_db.add(admin)
    test_db.commit()
    return admin


# ============================================================================
# ERP Fixtures
# ============================================================================


@pytest.fixture
def sample_product(test_db: Session, owner_business: Business) -> Product:
    """Create sample product."""
    product = Product(
        id=uuid4(),
        business_id=owner_business.id,
        sku="SKU-001",
        name="Widget Pro",
        product_type="physical",
        unit_price=99.99,
        tax_rate=0.00,
        is_active=True,
        track_inventory=True,
        weight_unit="kg",
        meta_data={},
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def sample_supplier(test_db: Session, owner_business: Business) -> Supplier:
    """Create sample supplier."""
    supplier = Supplier(
        id=uuid4(),
        business_id=owner_business.id,
        name="Acme Supplies",
        code="ACME",
        email="supply@acme.com",
        is_active=True,
        meta_data={},
    )
    test_db.add(supplier)
    test_db.commit()
    return supplier


@pytest.fixture
def sample_location(test_db: Session, owner_business: Business) -> InventoryLocation:
    """Create sample inventory location."""
    location = InventoryLocation(
        id=uuid4(),
        business_id=owner_business.id,
        name="Main Warehouse",
        code="WH-01",
        location_type="warehouse",
        is_active=True,
        meta_data={},
    )
    test_db.add(location)
    test_db.commit()
    return location


# ============================================================================
# Workflow Test Compatibility Fixtures
# ============================================================================


@pytest.fixture
def db(test_db: Session) -> Session:
    """Alias fixture for modules expecting `db`."""
    return test_db


@pytest.fixture
def business_id(owner_business: Business):
    """Business ID fixture expected by workflow tests."""
    return owner_business.id


@pytest.fixture
def other_business_id(other_business: Business):
    """Other business ID fixture expected by workflow tests."""
    return other_business.id


@pytest.fixture
def owner(owner_user: CurrentUser) -> dict:
    """Dictionary wrapper expected by workflow tests."""
    return {"user": owner_user}


@pytest.fixture
def manager(manager_user: CurrentUser) -> dict:
    """Dictionary wrapper expected by workflow tests."""
    return {"user": manager_user}


@pytest.fixture
def staff(staff_user: CurrentUser) -> dict:
    """Dictionary wrapper expected by workflow tests."""
    return {"user": staff_user}


@pytest.fixture
def other_owner(other_user: CurrentUser) -> dict:
    """Dictionary wrapper for user in another business."""
    return {"user": other_user}
