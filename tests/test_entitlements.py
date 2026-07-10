"""Plan-tier feature gating tests - starter/professional/enterprise limits,
and the legacy/trial full-access carve-out."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.services.organization import OrganizationService, TRIAL_PERIOD_DAYS


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


def _make_org_owner(test_db: Session, plan_tier: str, trial_ends_at: datetime | None = None) -> CurrentUser:
    """Create an Organization at a specific plan tier, with an owner user in
    its primary Business, and return a CurrentUser for that owner."""
    organization = Organization(
        id=uuid4(),
        name=f"{plan_tier.title()} Org",
        billing_email=f"{plan_tier}-org@{uuid4().hex[:8]}.com",
        plan_tier=plan_tier,
        trial_ends_at=trial_ends_at,
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


class TestTrialExpiry:
    """An expired trial loses access to everything, not just the
    require_feature-gated premium features - there's no paid tier under it
    to fall back to."""

    def test_active_trial_allowed(self, client, test_db: Session):
        user = _make_org_owner(test_db, "trial", trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7))
        r = client.get("/api/v1/customers", headers=_auth_headers(user))
        assert r.status_code == 200

    def test_expired_trial_forbidden_on_ungated_route(self, client, test_db: Session):
        # customers has no require_feature gate at all (every paying tier
        # gets basic CRM) - require_active_trial is the only thing blocking
        # this for an expired trial.
        user = _make_org_owner(test_db, "trial", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1))
        r = client.get("/api/v1/customers", headers=_auth_headers(user))
        assert r.status_code == 403
        assert "trial" in r.json()["detail"].lower()

    def test_expired_trial_can_still_read_org_status(self, client, test_db: Session):
        # organizations.router is deliberately exempt so the frontend can
        # render the "your trial ended, upgrade" prompt in the first place.
        user = _make_org_owner(test_db, "trial", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1))
        r = client.get("/api/v1/org", headers=_auth_headers(user))
        assert r.status_code == 200

    def test_other_tiers_unaffected_by_trial_ends_at(self, client, test_db: Session):
        # trial_ends_at is only meaningful for plan_tier == "trial" - a
        # paying tier is never blocked by require_active_trial regardless.
        user = _make_org_owner(test_db, "starter", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=30))
        r = client.get("/api/v1/customers", headers=_auth_headers(user))
        assert r.status_code == 200


class TestTrialProvisioning:
    """New trial-tier orgs get a 14-day trial_ends_at automatically."""

    def test_trial_tier_gets_trial_ends_at(self, test_db: Session):
        shell = OrganizationService(test_db).create_organization_shell(
            org_name="New Prospect", billing_email="prospect@example.com", plan_tier="trial"
        )
        test_db.commit()

        assert shell.organization.trial_ends_at is not None
        actual = shell.organization.trial_ends_at
        if actual.tzinfo is None:  # SQLite drops tzinfo on round-trip; it's always written as UTC
            actual = actual.replace(tzinfo=timezone.utc)
        expected = datetime.now(timezone.utc) + timedelta(days=TRIAL_PERIOD_DAYS)
        assert abs((actual - expected).total_seconds()) < 60

    def test_paid_tier_gets_no_trial_ends_at(self, test_db: Session):
        shell = OrganizationService(test_db).create_organization_shell(
            org_name="Paying Customer", billing_email="paying@example.com", plan_tier="starter"
        )
        test_db.commit()

        assert shell.organization.trial_ends_at is None


def _make_trial_org(test_db: Session, *, days_until_expiry: float, reminder_sent: bool = False) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Reminder Test Org",
        billing_email=f"reminder-{uuid4().hex[:8]}@example.com",
        plan_tier="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=days_until_expiry),
        trial_reminder_sent_at=datetime.now(timezone.utc) if reminder_sent else None,
    )
    test_db.add(org)
    test_db.commit()
    return org


class TestTrialReminders:
    """send_due_trial_reminders emails trial orgs nearing expiry, exactly once."""

    def test_sends_reminder_within_window(self, test_db: Session):
        org = _make_trial_org(test_db, days_until_expiry=2)

        with patch("app.services.organization.send_trial_reminder_email") as mock_send:
            sent = OrganizationService(test_db).send_due_trial_reminders()
            test_db.commit()

        assert sent == 1
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == org.billing_email
        test_db.refresh(org)
        assert org.trial_reminder_sent_at is not None

    def test_does_not_send_outside_window(self, test_db: Session):
        _make_trial_org(test_db, days_until_expiry=10)

        with patch("app.services.organization.send_trial_reminder_email") as mock_send:
            sent = OrganizationService(test_db).send_due_trial_reminders()

        assert sent == 0
        mock_send.assert_not_called()

    def test_does_not_send_twice(self, test_db: Session):
        _make_trial_org(test_db, days_until_expiry=2, reminder_sent=True)

        with patch("app.services.organization.send_trial_reminder_email") as mock_send:
            sent = OrganizationService(test_db).send_due_trial_reminders()

        assert sent == 0
        mock_send.assert_not_called()

    def test_does_not_send_for_non_trial_tier(self, test_db: Session):
        org = _make_trial_org(test_db, days_until_expiry=2)
        org.plan_tier = "starter"
        test_db.commit()

        with patch("app.services.organization.send_trial_reminder_email") as mock_send:
            sent = OrganizationService(test_db).send_due_trial_reminders()

        assert sent == 0
        mock_send.assert_not_called()

    def test_does_not_send_for_already_expired_trial(self, test_db: Session):
        _make_trial_org(test_db, days_until_expiry=-1)

        with patch("app.services.organization.send_trial_reminder_email") as mock_send:
            sent = OrganizationService(test_db).send_due_trial_reminders()

        assert sent == 0
        mock_send.assert_not_called()
