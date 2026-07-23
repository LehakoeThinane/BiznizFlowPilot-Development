"""Onboarding checklist tests - tier-filtering and per-step "done" detection,
plus the universal (not tier-gated) help-request endpoint."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.chat import ChatConversation, ChatMessage
from app.models.finance import Expense
from app.models.hr import Employee
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.models.workflow import WorkflowDefinition
from app.schemas.auth import CurrentUser


def _auth_headers(user: CurrentUser) -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": str(user.user_id),
            "business_id": str(user.business_id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _make_org_owner(test_db: Session, plan_tier: str) -> tuple[CurrentUser, Business, Organization]:
    """Create an Organization at a specific plan tier, with an owner user in
    its primary Business, and return (CurrentUser, Business, Organization)."""
    organization = Organization(
        id=uuid4(),
        name=f"{plan_tier.title()} Org",
        billing_email=f"{plan_tier}-org@{uuid4().hex[:8]}.com",
        plan_tier=plan_tier,
    )
    test_db.add(organization)
    test_db.commit()

    business = Business(
        id=uuid4(),
        organization_id=organization.id,
        name=f"{plan_tier.title()} Business",
        email=f"{plan_tier}-biz@{uuid4().hex[:8]}.com",
        phone="+1234567890",
        is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()

    user = User(
        id=uuid4(),
        business_id=business.id,
        email=f"{plan_tier}-owner@{uuid4().hex[:8]}.com",
        hashed_password=hash_password("password123"),
        first_name="Owner",
        last_name="User",
        role="owner",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()

    current_user = CurrentUser(
        user_id=str(user.id),
        business_id=str(business.id),
        organization_id=str(organization.id),
        email=user.email,
        role="owner",
        full_name=f"{user.first_name} {user.last_name}",
    )
    return current_user, business, organization


def _step_keys(response_json: dict) -> set[str]:
    return {step["key"] for step in response_json["steps"]}


def _step_done(response_json: dict, key: str) -> bool:
    return next(step["done"] for step in response_json["steps"] if step["key"] == key)


class TestChecklistTierFiltering:
    def test_starter_only_gets_tier_agnostic_steps(self, client, test_db: Session):
        user, _, _ = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert r.status_code == 200
        keys = _step_keys(r.json())
        assert keys == {"invite_team", "add_first_lead", "set_up_inventory"}

    def test_growth_gets_finance_automation_ai_but_not_hr(self, client, test_db: Session):
        user, _, _ = _make_org_owner(test_db, "growth")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert r.status_code == 200
        keys = _step_keys(r.json())
        assert {"explore_finance", "set_up_automation", "try_ai_copilot"} <= keys
        assert "set_up_hr" not in keys
        assert "add_subsidiary" not in keys

    def test_enterprise_gets_every_step(self, client, test_db: Session):
        user, _, _ = _make_org_owner(test_db, "enterprise")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert r.status_code == 200
        keys = _step_keys(r.json())
        assert keys == {
            "invite_team", "add_first_lead", "set_up_inventory",
            "explore_finance", "set_up_automation", "try_ai_copilot",
            "set_up_hr", "add_subsidiary",
        }


class TestChecklistDoneDetection:
    def test_invite_team_flips_done_once_a_second_user_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "invite_team") is False

        second = User(
            id=uuid4(), business_id=business.id, email=f"teammate-{uuid4().hex[:8]}@x.com",
            hashed_password=hash_password("password123"), first_name="Team", last_name="Mate",
            role="manager", is_active=True,
        )
        test_db.add(second)
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "invite_team") is True

    def test_add_first_lead_flips_done_once_a_lead_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "add_first_lead") is False

        test_db.add(Lead(id=uuid4(), business_id=business.id, status="new", source="web_form"))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "add_first_lead") is True

    def test_set_up_inventory_flips_done_once_a_product_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_inventory") is False

        test_db.add(Product(
            id=uuid4(), business_id=business.id, sku="SKU-001", name="Widget",
            product_type="physical", unit_price=99.99, tax_rate=0, is_active=True,
            track_inventory=True, weight_unit="kg", meta_data={},
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_inventory") is True

    def test_explore_finance_flips_done_once_an_expense_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "growth")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "explore_finance") is False

        test_db.add(Expense(
            id=uuid4(), business_id=business.id, date=date.today(),
            amount=100, description="Office supplies",
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "explore_finance") is True

    def test_set_up_automation_flips_done_once_a_workflow_definition_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "growth")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_automation") is False

        test_db.add(WorkflowDefinition(
            id=uuid4(), business_id=business.id, event_type=EventType.TASK_CREATED, is_active=True,
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_automation") is True

    def test_try_ai_copilot_flips_done_once_a_chat_message_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "growth")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "try_ai_copilot") is False

        conversation = ChatConversation(id=uuid4(), business_id=business.id, user_id=uuid4())
        test_db.add(conversation)
        test_db.commit()
        test_db.add(ChatMessage(
            id=uuid4(), conversation_id=conversation.id, role="user", content="Hi",
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "try_ai_copilot") is True

    def test_set_up_hr_flips_done_once_an_employee_exists(self, client, test_db: Session):
        user, business, _ = _make_org_owner(test_db, "enterprise")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_hr") is False

        test_db.add(Employee(
            id=uuid4(), business_id=business.id, first_name="Jane", last_name="Doe",
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "set_up_hr") is True

    def test_add_subsidiary_flips_done_once_a_second_business_exists(self, client, test_db: Session):
        user, _, organization = _make_org_owner(test_db, "enterprise")
        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "add_subsidiary") is False

        test_db.add(Business(
            id=uuid4(), organization_id=organization.id, name="Second Subsidiary",
            email=f"sub-{uuid4().hex[:8]}@x.com", phone="+1234567890", is_primary_subsidiary=False,
        ))
        test_db.commit()

        r = client.get("/api/v1/onboarding", headers=_auth_headers(user))
        assert _step_done(r.json(), "add_subsidiary") is True


class TestOnboardingHelpRequest:
    """Assistance is available regardless of tier - no FEATURE_TIERS gate."""

    def test_starter_can_request_help(self, client, test_db: Session):
        user, _, _ = _make_org_owner(test_db, "starter")
        r = client.post("/api/v1/onboarding/help", json={"note": "Stuck on invites"}, headers=_auth_headers(user))
        assert r.status_code == 204

    def test_enterprise_can_request_help(self, client, test_db: Session):
        user, _, _ = _make_org_owner(test_db, "enterprise")
        r = client.post("/api/v1/onboarding/help", json={}, headers=_auth_headers(user))
        assert r.status_code == 204
