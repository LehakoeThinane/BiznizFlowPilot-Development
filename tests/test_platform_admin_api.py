"""API tests for the platform admin console (cross-tenant, vendor staff only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import create_access_token, create_platform_access_token
from app.models.business import Business
from app.models.organization import Organization
from app.models.platform_admin import PlatformAdmin
from app.schemas.auth import CurrentUser


def _platform_headers(admin: PlatformAdmin) -> dict[str, str]:
    token = create_platform_access_token(
        {
            "platform_admin_id": str(admin.id),
            "email": admin.email,
            "full_name": admin.full_name,
            "platform_role": admin.platform_role,
            "impersonation_allowed": admin.impersonation_allowed,
            "phash": admin.hashed_password[-8:],
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _tenant_headers(user: CurrentUser) -> dict[str, str]:
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


PROVISION_BODY = {
    "org_name": "Acme Client Co",
    "billing_email": "billing@acmeclient.com",
    "owner_email": "owner@acmeclient.com",
}


class TestPlatformStats:
    def test_requires_platform_auth(self, client):
        r = client.get("/platform/v1/stats")
        assert r.status_code == 401

    def test_returns_counts(self, client, platform_admin: PlatformAdmin, owner_business: Business):
        r = client.get("/platform/v1/stats", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        body = r.json()
        assert "organizations_by_plan_tier" in body
        assert "mrr_zar" in body
        assert "trial_conversion_rate" in body

    def test_mrr_and_conversion_rate(self, client, test_db, platform_admin: PlatformAdmin):
        now = datetime.now(timezone.utc)
        # One converted trial (still has trial_ends_at, now on a paid tier).
        test_db.add(
            Organization(
                id=uuid4(),
                name="Converted Co",
                billing_email="converted@example.com",
                plan_tier="professional",
                trial_ends_at=now - timedelta(days=5),
            )
        )
        # One still-active trial (not yet converted, not yet expired).
        test_db.add(
            Organization(
                id=uuid4(),
                name="Still Trialing Co",
                billing_email="trialing@example.com",
                plan_tier="trial",
                trial_ends_at=now + timedelta(days=5),
            )
        )
        # One starter-tier org that never went through a trial (no trial_ends_at) - excluded from the cohort.
        test_db.add(
            Organization(
                id=uuid4(), name="Direct Starter Co", billing_email="direct@example.com", plan_tier="starter"
            )
        )
        test_db.commit()

        r = client.get("/platform/v1/stats", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        body = r.json()

        # Trial cohort = 2 (converted + still trialing); 1 of 2 converted = 50%.
        assert body["trial_conversion_rate"] == 0.5
        # MRR only counts starter/professional orgs: R35,000 (professional) + R8,750 (starter) = R43,750.
        assert body["mrr_zar"] == 43750
        assert body["organizations_by_plan_tier"]["professional"] >= 1
        assert body["organizations_by_plan_tier"]["trial"] >= 1


class TestPlatformTenants:
    def test_list_tenants(self, client, platform_admin: PlatformAdmin, owner_business: Business):
        r = client.get("/platform/v1/tenants", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        names = [t["name"] for t in r.json()]
        assert "Owner Business" in names

    def test_get_tenant_detail(self, client, platform_admin: PlatformAdmin, owner_business: Business):
        r = client.get(
            f"/platform/v1/tenants/{owner_business.id}", headers=_platform_headers(platform_admin)
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(owner_business.id)

    def test_get_tenant_not_found(self, client, platform_admin: PlatformAdmin):
        r = client.get(f"/platform/v1/tenants/{uuid4()}", headers=_platform_headers(platform_admin))
        assert r.status_code == 404

    def test_toggle_user_active(self, client, platform_admin: PlatformAdmin, owner_user: CurrentUser):
        r = client.patch(
            f"/platform/v1/users/{owner_user.user_id}",
            params={"is_active": False},
            headers=_platform_headers(platform_admin),
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False


class TestPlatformOrganizations:
    def test_list_organizations(self, client, platform_admin: PlatformAdmin, owner_business: Business):
        r = client.get("/platform/v1/organizations", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_provision_new_organization(self, client, platform_admin: PlatformAdmin, monkeypatch):
        """Provisioning creates the org shell and invites the owner - no User yet.

        No password is collected from the platform admin; the owner sets their
        own credentials by accepting the emailed invite (see InvitationService).
        """
        captured = {}

        def _fake_send_invite_email(**kwargs):
            captured["raw_token"] = kwargs["raw_token"]

        monkeypatch.setattr("app.services.email.send_invite_email", _fake_send_invite_email)

        r = client.post(
            "/platform/v1/organizations", json=PROVISION_BODY, headers=_platform_headers(platform_admin)
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Acme Client Co"
        assert body["subsidiary_count"] == 1
        assert body["user_count"] == 0

        # Owner accepts the invite, setting their own password, and can then log in.
        raw_token = captured["raw_token"]
        accept = client.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": raw_token,
                "password": "password123",
                "first_name": "Jane",
                "last_name": "Doe",
            },
        )
        assert accept.status_code == 200
        assert "access_token" in accept.json()

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@acmeclient.com", "password": "password123"},
        )
        assert login.status_code == 200

    def test_provision_rejects_owner_email_of_existing_active_user(
        self, client, platform_admin: PlatformAdmin, monkeypatch
    ):
        """Provisioning a second organization for an email that already has an
        active account (from a prior accepted invite) is rejected."""
        captured = {}
        monkeypatch.setattr(
            "app.services.email.send_invite_email",
            lambda **kwargs: captured.update(raw_token=kwargs["raw_token"]),
        )
        headers = _platform_headers(platform_admin)  # captured once - fixture detaches after first request

        client.post("/platform/v1/organizations", json=PROVISION_BODY, headers=headers)
        client.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": captured["raw_token"],
                "password": "password123",
                "first_name": "Jane",
                "last_name": "Doe",
            },
        )

        r = client.post("/platform/v1/organizations", json=PROVISION_BODY, headers=headers)
        assert r.status_code == 400

    def test_provision_requires_platform_auth(self, client):
        r = client.post("/platform/v1/organizations", json=PROVISION_BODY)
        assert r.status_code == 401

    def test_get_organization_detail(self, client, platform_admin: PlatformAdmin):
        headers = _platform_headers(platform_admin)  # captured once - fixture detaches after first request
        created = client.post("/platform/v1/organizations", json=PROVISION_BODY, headers=headers).json()
        r = client.get(f"/platform/v1/organizations/{created['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_update_organization_plan_tier(self, client, platform_admin: PlatformAdmin):
        headers = _platform_headers(platform_admin)  # captured once - fixture detaches after first request
        created = client.post("/platform/v1/organizations", json=PROVISION_BODY, headers=headers).json()
        r = client.patch(
            f"/platform/v1/organizations/{created['id']}",
            json={"plan_tier": "enterprise", "seats_included": 100},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["plan_tier"] == "enterprise"
        assert r.json()["seats_included"] == 100

    def test_tenant_it_admin_cannot_touch_plan_tier(self, client, org_admin_user: CurrentUser):
        """plan_tier/subscription_status are platform-only - a plan_tier field sent to the
        tenant org route is silently ignored (OrganizationUpdate has no such field)."""
        r = client.patch(
            "/api/v1/org",
            json={"name": "New Name", "plan_tier": "enterprise"},
            headers=_tenant_headers(org_admin_user),
        )
        assert r.status_code == 200
        assert r.json()["plan_tier"] != "enterprise"


class TestPlatformAdminManagement:
    def test_get_my_profile(self, client, platform_admin: PlatformAdmin):
        r = client.get("/platform/v1/admins/me", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        assert r.json()["email"] == platform_admin.email

    def test_support_role_cannot_create_admin(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/admins",
            json={
                "email": "new-admin@vendor.example.com",
                "password": "password123",
                "full_name": "New Admin",
                "platform_role": "support",
            },
            headers=_platform_headers(platform_admin),
        )
        assert r.status_code == 403

    def test_super_admin_can_create_admin(self, client, platform_super_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/admins",
            json={
                "email": "new-admin@vendor.example.com",
                "password": "password123",
                "full_name": "New Admin",
                "platform_role": "billing_ops",
            },
            headers=_platform_headers(platform_super_admin),
        )
        assert r.status_code == 201
        assert r.json()["platform_role"] == "billing_ops"

    def test_create_admin_duplicate_email_rejected(self, client, platform_super_admin: PlatformAdmin):
        headers = _platform_headers(platform_super_admin)  # captured once - fixture detaches after first request
        body = {
            "email": "dupe-admin@vendor.example.com",
            "password": "password123",
            "full_name": "Dupe Admin",
            "platform_role": "support",
        }
        client.post("/platform/v1/admins", json=body, headers=headers)
        r = client.post("/platform/v1/admins", json=body, headers=headers)
        assert r.status_code == 400


class TestPlatformAdminChangePassword:
    def test_wrong_current_password_rejected(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/admins/me/change-password",
            json={"current_password": "wrong-password", "new_password": "newpassword456"},
            headers=_platform_headers(platform_admin),
        )
        assert r.status_code == 400

    def test_too_short_new_password_rejected(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/admins/me/change-password",
            json={"current_password": "password123", "new_password": "short"},
            headers=_platform_headers(platform_admin),
        )
        assert r.status_code == 422

    def test_successful_change_allows_login_with_new_password(self, client, platform_admin: PlatformAdmin):
        email = platform_admin.email  # captured once - fixture detaches after first request
        r = client.post(
            "/platform/v1/admins/me/change-password",
            json={"current_password": "password123", "new_password": "newpassword456"},
            headers=_platform_headers(platform_admin),
        )
        assert r.status_code == 200

        r = client.post(
            "/platform/v1/auth/login",
            json={"email": email, "password": "newpassword456"},
        )
        assert r.status_code == 200

        r = client.post(
            "/platform/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert r.status_code == 401

    def test_old_token_rejected_after_password_change(self, client, platform_admin: PlatformAdmin):
        stale_headers = _platform_headers(platform_admin)
        client.post(
            "/platform/v1/admins/me/change-password",
            json={"current_password": "password123", "new_password": "newpassword456"},
            headers=stale_headers,
        )
        r = client.get("/platform/v1/admins/me", headers=stale_headers)
        assert r.status_code == 401


class TestPlatformCrossTenantIsolationFromDashboard:
    """A tenant user, even an owner, must never reach platform endpoints."""

    def test_owner_cannot_list_organizations(self, client, owner_user: CurrentUser):
        r = client.get("/platform/v1/organizations", headers=_tenant_headers(owner_user))
        assert r.status_code == 401

    def test_owner_cannot_provision_organization(self, client, owner_user: CurrentUser):
        r = client.post(
            "/platform/v1/organizations", json=PROVISION_BODY, headers=_tenant_headers(owner_user)
        )
        assert r.status_code == 401
