"""API tests for platform (vendor staff) authentication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token, create_platform_access_token
from app.models.platform_admin import PlatformAdmin


class TestPlatformLogin:
    def test_valid_credentials_returns_tokens(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "password123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_rejected(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "wrong-password"},
        )
        assert r.status_code == 401

    def test_unknown_email_rejected(self, client):
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": "nobody@vendor.example.com", "password": "password123"},
        )
        assert r.status_code == 401

    def test_inactive_admin_rejected(self, client, test_db, platform_admin: PlatformAdmin):
        platform_admin.is_active = False
        test_db.commit()
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "password123"},
        )
        assert r.status_code == 401

    def test_lockout_after_max_failed_attempts(self, client, platform_admin: PlatformAdmin):
        email = platform_admin.email  # captured before any request detaches the fixture's session
        for _ in range(5):
            client.post(
                "/platform/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert r.status_code == 401
        assert "locked" in r.json()["detail"].lower()

    def test_login_sets_platform_cookies_not_tenant_cookies(self, client, platform_admin: PlatformAdmin):
        r = client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "password123"},
        )
        assert "bfp_platform_access" in r.cookies
        assert "bfp_platform_refresh" in r.cookies
        assert "bfp_access" not in r.cookies


class TestPlatformRefresh:
    def test_refresh_with_cookie(self, client, platform_admin: PlatformAdmin):
        login = client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "password123"},
        )
        assert login.status_code == 200
        r = client.post("/platform/v1/auth/refresh")
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_refresh_missing_token_rejected(self, client):
        r = client.post("/platform/v1/auth/refresh")
        assert r.status_code == 401

    def test_tenant_refresh_token_rejected_on_platform_refresh(self, client, owner_user):
        tenant_access = create_access_token(
            {
                "user_id": str(owner_user.user_id),
                "business_id": str(owner_user.business_id),
                "email": owner_user.email,
                "role": owner_user.role,
                "full_name": owner_user.full_name,
            }
        )
        r = client.post("/platform/v1/auth/refresh", json={"refresh_token": tenant_access})
        assert r.status_code == 401


class TestPlatformLogout:
    def test_logout_clears_cookies(self, client, platform_admin: PlatformAdmin):
        client.post(
            "/platform/v1/auth/login",
            json={"email": platform_admin.email, "password": "password123"},
        )
        r = client.post("/platform/v1/auth/logout")
        assert r.status_code == 200


class TestPlatformTokenIsolation:
    """The core auth-boundary invariant: platform and tenant tokens must never cross-validate."""

    def test_platform_token_rejected_by_tenant_endpoint(self, client, platform_admin: PlatformAdmin):
        token = create_platform_access_token(
            {
                "platform_admin_id": str(platform_admin.id),
                "email": platform_admin.email,
                "full_name": platform_admin.full_name,
                "platform_role": platform_admin.platform_role,
                "impersonation_allowed": platform_admin.impersonation_allowed,
                "phash": platform_admin.hashed_password[-8:],
            }
        )
        r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_tenant_token_rejected_by_platform_endpoint(self, client, owner_user):
        tenant_token = create_access_token(
            {
                "user_id": str(owner_user.user_id),
                "business_id": str(owner_user.business_id),
                "email": owner_user.email,
                "role": owner_user.role,
                "full_name": owner_user.full_name,
            }
        )
        r = client.get("/platform/v1/stats", headers={"Authorization": f"Bearer {tenant_token}"})
        assert r.status_code == 401

    def test_expired_platform_token_rejected(self, client, platform_admin: PlatformAdmin):
        token = create_platform_access_token(
            {
                "platform_admin_id": str(platform_admin.id),
                "email": platform_admin.email,
                "full_name": platform_admin.full_name,
                "platform_role": platform_admin.platform_role,
                "impersonation_allowed": platform_admin.impersonation_allowed,
            },
            expires_delta=timedelta(seconds=-1),
        )
        r = client.get("/platform/v1/stats", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_password_change_invalidates_outstanding_token(
        self, client, test_db, platform_admin: PlatformAdmin
    ):
        token = create_platform_access_token(
            {
                "platform_admin_id": str(platform_admin.id),
                "email": platform_admin.email,
                "full_name": platform_admin.full_name,
                "platform_role": platform_admin.platform_role,
                "impersonation_allowed": platform_admin.impersonation_allowed,
                "phash": platform_admin.hashed_password[-8:],
            }
        )
        from app.core.security import hash_password

        platform_admin.hashed_password = hash_password("a-new-password")
        test_db.commit()

        r = client.get("/platform/v1/stats", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401
