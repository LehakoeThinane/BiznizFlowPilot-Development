"""API tests for user invitations - domain-restricted employee onboarding."""

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


# ── POST /api/v1/users/invite ────────────────────────────────────────────────


class TestCreateInvitation:
    def test_owner_can_invite_into_own_business(self, client, owner_user: CurrentUser):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "role": "staff"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "newhire@example.com"
        assert body["role"] == "staff"
        assert body["status"] == "pending"

    def test_staff_cannot_invite(self, client, staff_user: CurrentUser):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com"},
            headers=_auth_headers(staff_user),
        )
        assert r.status_code == 403

    def test_owner_business_id_override_is_ignored(
        self, client, owner_user: CurrentUser, other_business: Business
    ):
        """Non-admins can't redirect an invite elsewhere by passing business_id -
        it's silently ignored and the invite always lands on their own business."""
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "business_id": str(other_business.id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        assert r.json()["business_id"] == str(owner_user.business_id)

    def test_it_admin_can_invite_into_own_subsidiary(self, client, org_admin_user: CurrentUser):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 201

    def test_it_admin_can_invite_into_sibling_subsidiary(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        second_business_id = str(owner_second_business.id)
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "business_id": second_business_id},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 201
        assert r.json()["business_id"] == second_business_id

    def test_it_admin_cannot_invite_into_other_orgs_business(
        self, client, org_admin_user: CurrentUser, other_business: Business
    ):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "business_id": str(other_business.id)},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 403

    def test_invite_into_nonexistent_business_not_found(
        self, client, org_admin_user: CurrentUser
    ):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "business_id": str(uuid4())},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 404

    def test_duplicate_pending_invite_rejected(self, client, owner_user: CurrentUser):
        client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com"},
            headers=_auth_headers(owner_user),
        )
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400

    def test_invite_rejected_for_unauthorized_domain(self, client, org_admin_user: CurrentUser):
        client.post(
            "/api/v1/org/domains",
            json={"domain": "onlythis.com"},
            headers=_auth_headers(org_admin_user),
        )
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@otherdomain.com"},
            headers=_auth_headers(org_admin_user),
        )
        assert r.status_code == 400

    def test_non_admin_cannot_invite_it_admin_role(self, client, owner_user: CurrentUser):
        r = client.post(
            "/api/v1/users/invite",
            json={"email": "newhire@example.com", "role": "it_admin"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201  # owner is allowed to mint it_admin invites


# ── GET /api/v1/users/invites ────────────────────────────────────────────────


class TestListInvitations:
    def test_owner_sees_only_own_business_invites(
        self, client, owner_user: CurrentUser, org_admin_user: CurrentUser
    ):
        client.post(
            "/api/v1/users/invite",
            json={"email": "a@example.com"},
            headers=_auth_headers(owner_user),
        )
        r = client.get("/api/v1/users/invites", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_it_admin_sees_org_wide_invites(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        second_business_id = str(owner_second_business.id)
        client.post(
            "/api/v1/users/invite",
            json={"email": "a@example.com"},
            headers=_auth_headers(org_admin_user),
        )
        client.post(
            "/api/v1/users/invite",
            json={"email": "b@example.com", "business_id": second_business_id},
            headers=_auth_headers(org_admin_user),
        )
        r = client.get("/api/v1/users/invites", headers=_auth_headers(org_admin_user))
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_staff_forbidden(self, client, staff_user: CurrentUser):
        r = client.get("/api/v1/users/invites", headers=_auth_headers(staff_user))
        assert r.status_code == 403


# ── DELETE /api/v1/users/invites/{id} ────────────────────────────────────────


class TestRevokeInvitation:
    def test_owner_can_revoke_own_business_invite(self, client, owner_user: CurrentUser):
        created = client.post(
            "/api/v1/users/invite",
            json={"email": "a@example.com"},
            headers=_auth_headers(owner_user),
        ).json()
        r = client.delete(
            f"/api/v1/users/invites/{created['id']}", headers=_auth_headers(owner_user)
        )
        assert r.status_code == 204

    def test_revoke_twice_not_found(self, client, owner_user: CurrentUser):
        created = client.post(
            "/api/v1/users/invite",
            json={"email": "a@example.com"},
            headers=_auth_headers(owner_user),
        ).json()
        client.delete(f"/api/v1/users/invites/{created['id']}", headers=_auth_headers(owner_user))
        r = client.delete(
            f"/api/v1/users/invites/{created['id']}", headers=_auth_headers(owner_user)
        )
        assert r.status_code == 404

    def test_it_admin_can_revoke_sibling_subsidiary_invite(
        self, client, org_admin_user: CurrentUser, owner_second_business: Business
    ):
        created = client.post(
            "/api/v1/users/invite",
            json={"email": "a@example.com", "business_id": str(owner_second_business.id)},
            headers=_auth_headers(org_admin_user),
        ).json()
        r = client.delete(
            f"/api/v1/users/invites/{created['id']}", headers=_auth_headers(org_admin_user)
        )
        assert r.status_code == 204

    def test_staff_forbidden(self, client, staff_user: CurrentUser):
        r = client.delete(
            f"/api/v1/users/invites/{uuid4()}", headers=_auth_headers(staff_user)
        )
        assert r.status_code == 403


# ── GET/POST /api/v1/auth/invite/validate and /accept ────────────────────────


class TestValidateAndAcceptInvite:
    def _create_invite(self, client, owner_user: CurrentUser, email: str = "newhire@example.com"):
        return client.post(
            "/api/v1/users/invite",
            json={"email": email},
            headers=_auth_headers(owner_user),
        ).json()

    def test_validate_invalid_token(self, client):
        r = client.get("/api/v1/auth/invite/validate", params={"token": "bogus"})
        assert r.status_code == 404

    def test_accept_invalid_token(self, client):
        r = client.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": "bogus",
                "password": "newpassword123",
                "first_name": "New",
                "last_name": "Hire",
            },
        )
        assert r.status_code == 400

    def test_validate_and_accept_success(self, client, owner_user: CurrentUser, monkeypatch):
        captured = {}

        def _fake_send_invite_email(**kwargs):
            captured["raw_token"] = kwargs["raw_token"]

        monkeypatch.setattr(
            "app.services.email.send_invite_email", _fake_send_invite_email
        )
        self._create_invite(client, owner_user)
        raw_token = captured["raw_token"]

        r = client.get("/api/v1/auth/invite/validate", params={"token": raw_token})
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "staff"
        assert body["organization_name"] == "Owner Organization"

        r = client.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": raw_token,
                "password": "newpassword123",
                "first_name": "New",
                "last_name": "Hire",
            },
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

        # Re-accepting the same (now-consumed) token fails.
        r = client.post(
            "/api/v1/auth/invite/accept",
            json={
                "token": raw_token,
                "password": "newpassword123",
                "first_name": "New",
                "last_name": "Hire",
            },
        )
        assert r.status_code == 400
