"""Plan-tier feature gating tests - starter/professional/enterprise limits,
and the legacy/trial full-access carve-out."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
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


def _make_org_owner(test_db: Session, plan_tier: str) -> CurrentUser:
    """Create an Organization at a specific plan tier, with an owner user in
    its primary Business, and return a CurrentUser for that owner."""
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

    return CurrentUser(
        user_id=str(user.id),
        business_id=str(business.id),
        organization_id=str(organization.id),
        email=user.email,
        role="owner",
        full_name=f"{user.first_name} {user.last_name}",
    )


class TestStarterTierGating:
    """Starter gets none of the gated features."""

    def test_hr_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/hr/departments", headers=_auth_headers(user))
        assert r.status_code == 403

    def test_finance_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        r = client.get("/api/v1/finance/summary", headers=_auth_headers(user))
        assert r.status_code == 403

    def test_ai_chat_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        r = client.post(
            "/api/v1/chat/message", json={"message": "hi"}, headers=_auth_headers(user)
        )
        assert r.status_code == 403

    def test_workflow_definition_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        r = client.post(
            "/api/v1/workflow-definitions",
            json={"event_type": "task_created", "name": "Test Workflow"},
            headers=_auth_headers(user),
        )
        assert r.status_code == 403

    def test_second_location_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "starter")
        headers = _auth_headers(user)
        first = client.post(
            "/api/v1/inventory/locations",
            json={"name": "Main Warehouse", "location_type": "warehouse"},
            headers=headers,
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/inventory/locations",
            json={"name": "Second Warehouse", "location_type": "warehouse"},
            headers=headers,
        )
        assert second.status_code == 403


class TestProfessionalTierGating:
    """Professional gets finance/chat/workflows/orders, but not HR."""

    def test_hr_still_forbidden(self, client, test_db: Session):
        user = _make_org_owner(test_db, "professional")
        r = client.get("/api/v1/hr/departments", headers=_auth_headers(user))
        assert r.status_code == 403

    def test_finance_allowed(self, client, test_db: Session):
        user = _make_org_owner(test_db, "professional")
        r = client.get("/api/v1/finance/summary", headers=_auth_headers(user))
        assert r.status_code == 200


class TestFullAccessTiers:
    """legacy and trial both get through every gate."""

    def test_legacy_hr_allowed(self, client, test_db: Session):
        user = _make_org_owner(test_db, "legacy")
        r = client.get("/api/v1/hr/departments", headers=_auth_headers(user))
        assert r.status_code == 200

    def test_trial_hr_allowed(self, client, test_db: Session):
        user = _make_org_owner(test_db, "trial")
        r = client.get("/api/v1/hr/departments", headers=_auth_headers(user))
        assert r.status_code == 200

    def test_enterprise_hr_allowed(self, client, test_db: Session):
        user = _make_org_owner(test_db, "enterprise")
        r = client.get("/api/v1/hr/departments", headers=_auth_headers(user))
        assert r.status_code == 200
