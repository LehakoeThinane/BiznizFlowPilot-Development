"""API tests for the platform admin console (cross-tenant, vendor staff only)."""

from __future__ import annotations

from uuid import uuid4

from app.core.security import create_access_token, create_platform_access_token
from app.models.business import Business
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
    "owner_password": "password123",
    "owner_first_name": "Jane",
    "owner_last_name": "Doe",
}


class TestPlatformStats:
    def test_requires_platform_auth(self, client):
        r = client.get("/platform/v1/stats")
        assert r.status_code == 401

    def test_returns_counts(self, client, platform_admin: PlatformAdmin, owner_business: Business):
        r = client.get("/platform/v1/stats", headers=_platform_headers(platform_admin))
        assert r.status_code == 200
        body = r.json()
        assert body["total_organizations"] >= 1
        assert body["total_tenants"] >= 1


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

    def test_provision_new_organization(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/organizations", json=PROVISION_BODY, headers=_platform_headers(platform_admin)
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Acme Client Co"
        assert body["subsidiary_count"] == 1
        assert body["user_count"] == 1

        # Owner can now log in through the normal tenant login flow.
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@acmeclient.com", "password": "password123"},
        )
        assert login.status_code == 200

    def test_provision_duplicate_owner_email_rejected(self, client, platform_admin: PlatformAdmin):
        headers = _platform_headers(platform_admin)  # captured once - fixture detaches after first request
        client.post("/platform/v1/organizations", json=PROVISION_BODY, headers=headers)
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
