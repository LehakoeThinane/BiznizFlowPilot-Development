"""API tests for organization/subsidiary management (IT Admin own-org scope)."""

from __future__ import annotations

from uuid import uuid4

from app.core.security import create_access_token
from app.models.business import Business
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


# ── GET /api/v1/org ─────────────────────────────────────────────────────────


class TestGetOrganization:
    def test_any_authenticated_user_can_view(self, client, owner_user: CurrentUser):
        r = client.get("/api/v1/org", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Owner Organization"
        assert body["domains"] == []

    def test_includes_added_domains(self, client, org_admin_user: CurrentUser):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "example.com", "is_primary": True},
            headers=_auth_headers(org_admin_user),
        )
        r = client.get("/api/v1/org", headers=_auth_headers(org_admin_user))
        assert r.status_code == 200
        assert r.json()["domains"] == ["example.com"]

    def test_unauthenticated_rejected(self, client):
        r = client.get("/api/v1/org")
        assert r.status_code == 401


# ── PATCH /api/v1/org ────────────────────────────────────────────────────────


class TestUpdateOrganization:
    def test_it_admin_can_update_name(self, client, org_admin_user: CurrentUser):
        r = client.patch(
            "/api/v1/org", json={"name": "Renamed Org"}, headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed Org"

    def test_owner_forbidden(self, client, owner_user: CurrentUser):
        r = client.patch(
            "/api/v1/org", json={"name": "Renamed Org"}, headers=_auth_headers(owner_user)
        )
        assert r.status_code == 403

    def test_staff_forbidden(self, client, staff_user: CurrentUser):
        r = client.patch(
            "/api/v1/org", json={"name": "Renamed Org"}, headers=_auth_headers(staff_user)
        )
        assert r.status_code == 403


# ── Domains ──────────────────────────────────────────────────────────────────


class TestOrganizationDomains:
    def test_add_and_list_domain(self, client, org_admin_user: CurrentUser):
        r = client.post(
            "/api/v1/org/domains",
            json={"domain": "acme.com", "is_primary": False},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 201
        assert r.json()["domain"] == "acme.com"

        r = client.get("/api/v1/org/domains", headers=_auth_headers(org_admin_user))
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_duplicate_domain_rejected(self, client, org_admin_user: CurrentUser):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "acme.com"},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/org/domains",
            json={"domain": "acme.com"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 400

    def test_remove_domain(self, client, org_admin_user: CurrentUser):
        created = client.post(
            "/api/v1/org/domains",
            json={"domain": "acme.com"},
            headers=_auth_headers(org_admin_user),
        ).json()
        r = client.delete(
            f"/api/v1/org/domains/{created['id']}", headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 204
        assert client.get("/api/v1/org/domains", headers=_auth_headers(org_admin_user)).json() == []

    def test_remove_nonexistent_domain(self, client, org_admin_user: CurrentUser):
        r = client.delete(
            f"/api/v1/org/domains/{uuid4()}", headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 404

    def test_non_admin_forbidden(self, client, owner_user: CurrentUser):
        r = client.get("/api/v1/org/domains", headers=_auth_headers(owner_user))
        assert r.status_code == 403


# ── Subsidiaries ─────────────────────────────────────────────────────────────


class TestSubsidiaries:
    def test_list_includes_primary_business(self, client, org_admin_user: CurrentUser):
        r = client.get("/api/v1/org/subsidiaries", headers=_auth_headers(org_admin_user))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["is_primary_subsidiary"] is True

    def test_create_subsidiary(self, client, org_admin_user: CurrentUser):
        r = client.post(
            "/api/v1/org/subsidiaries",
            json={"name": "New Sub", "email": "newsub@example.com", "phone": "+15551234567"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "New Sub"
        assert body["is_primary_subsidiary"] is False
        assert body["user_count"] == 0

    def test_create_subsidiary_duplicate_email_rejected(self, client, org_admin_user: CurrentUser):
        client.post(
            "/api/v1/org/subsidiaries",
            json={"name": "Sub A", "email": "dupe@example.com"},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/org/subsidiaries",
            json={"name": "Sub B", "email": "dupe@example.com"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 400

    def test_create_subsidiary_non_admin_forbidden(self, client, owner_user: CurrentUser):
        r = client.post(
            "/api/v1/org/subsidiaries",
            json={"name": "New Sub", "email": "newsub@example.com"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 403

    def test_get_subsidiary_same_org(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        r = client.get(
            f"/api/v1/org/subsidiaries/{owner_second_business.id}",
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 200
        assert r.json()["id"] == str(owner_second_business.id)

    def test_get_subsidiary_not_found(self, client, org_admin_user: CurrentUser):
        r = client.get(
            f"/api/v1/org/subsidiaries/{uuid4()}", headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 404

    def test_get_subsidiary_cross_org_forbidden(
        self, client, org_admin_user: CurrentUser, other_business: Business
    ):
        r = client.get(
            f"/api/v1/org/subsidiaries/{other_business.id}",
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 403

    def test_update_subsidiary(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        r = client.patch(
            f"/api/v1/org/subsidiaries/{owner_second_business.id}",
            json={"name": "Renamed Sub"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed Sub"

    def test_update_subsidiary_cross_org_forbidden(
        self, client, org_admin_user: CurrentUser, other_business: Business
    ):
        r = client.patch(
            f"/api/v1/org/subsidiaries/{other_business.id}",
            json={"name": "Hijacked"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 403

    def test_deactivate_subsidiary(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        second_business_id = str(owner_second_business.id)
        r = client.delete(
            f"/api/v1/org/subsidiaries/{second_business_id}",
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 204
        listing = client.get(
            "/api/v1/org/subsidiaries", headers=_auth_headers(org_admin_user)
        ).json()
        sub = next(i for i in listing["items"] if i["id"] == second_business_id)
        assert sub["is_active"] is False

    def test_cannot_deactivate_primary_subsidiary(
        self, client, org_admin_user: CurrentUser, owner_business: Business
    ):
        r = client.delete(
            f"/api/v1/org/subsidiaries/{owner_business.id}",
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 400

    def test_deactivate_nonexistent_subsidiary(self, client, org_admin_user: CurrentUser):
        r = client.delete(
            f"/api/v1/org/subsidiaries/{uuid4()}", headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 404
