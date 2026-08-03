"""API tests for marketing CMS (MM Nexus blog admin) authentication."""

from __future__ import annotations

from datetime import timedelta

from app.core.security import create_access_token, create_marketing_cms_access_token, create_platform_access_token
from app.models.marketing_cms_admin import MarketingCmsAdmin


class TestMarketingCmsLogin:
    def test_valid_credentials_returns_tokens(self, client, marketing_cms_admin: MarketingCmsAdmin):
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "password123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_rejected(self, client, marketing_cms_admin: MarketingCmsAdmin):
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "wrong-password"},
        )
        assert r.status_code == 401

    def test_unknown_email_rejected(self, client):
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": "nobody@mmnexus.co.za", "password": "password123"},
        )
        assert r.status_code == 401

    def test_inactive_admin_rejected(self, client, test_db, marketing_cms_admin: MarketingCmsAdmin):
        marketing_cms_admin.is_active = False
        test_db.commit()
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "password123"},
        )
        assert r.status_code == 401

    def test_lockout_after_max_failed_attempts(self, client, marketing_cms_admin: MarketingCmsAdmin):
        email = marketing_cms_admin.email
        for _ in range(5):
            client.post(
                "/api/v1/marketing/cms/auth/login",
                json={"email": email, "password": "wrong-password"},
            )
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert r.status_code == 401
        assert "locked" in r.json()["detail"].lower()

    def test_login_sets_marketing_cms_cookies_not_tenant_or_platform_cookies(
        self, client, marketing_cms_admin: MarketingCmsAdmin
    ):
        r = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "password123"},
        )
        assert "bfp_mcms_access" in r.cookies
        assert "bfp_mcms_refresh" in r.cookies
        assert "bfp_access" not in r.cookies
        assert "bfp_platform_access" not in r.cookies


class TestMarketingCmsRefresh:
    def test_refresh_with_cookie(self, client, marketing_cms_admin: MarketingCmsAdmin):
        login = client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "password123"},
        )
        assert login.status_code == 200
        r = client.post("/api/v1/marketing/cms/auth/refresh")
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_refresh_missing_token_rejected(self, client):
        r = client.post("/api/v1/marketing/cms/auth/refresh")
        assert r.status_code == 401


class TestMarketingCmsLogout:
    def test_logout_clears_cookies(self, client, marketing_cms_admin: MarketingCmsAdmin):
        client.post(
            "/api/v1/marketing/cms/auth/login",
            json={"email": marketing_cms_admin.email, "password": "password123"},
        )
        r = client.post("/api/v1/marketing/cms/auth/logout")
        assert r.status_code == 200


class TestMarketingCmsTokenIsolation:
    """The core auth-boundary invariant: marketing-CMS tokens must never
    cross-validate against tenant or platform-admin endpoints, and vice versa."""

    def test_marketing_cms_token_rejected_by_tenant_endpoint(self, client, marketing_cms_admin: MarketingCmsAdmin):
        token = create_marketing_cms_access_token(
            {
                "marketing_cms_admin_id": str(marketing_cms_admin.id),
                "email": marketing_cms_admin.email,
                "full_name": marketing_cms_admin.full_name,
                "phash": marketing_cms_admin.hashed_password[-8:],
            }
        )
        r = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_marketing_cms_token_rejected_by_platform_endpoint(self, client, marketing_cms_admin: MarketingCmsAdmin):
        token = create_marketing_cms_access_token(
            {
                "marketing_cms_admin_id": str(marketing_cms_admin.id),
                "email": marketing_cms_admin.email,
                "full_name": marketing_cms_admin.full_name,
                "phash": marketing_cms_admin.hashed_password[-8:],
            }
        )
        r = client.get("/platform/v1/stats", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_tenant_token_rejected_by_marketing_cms_endpoint(self, client, owner_user):
        tenant_token = create_access_token(
            {
                "user_id": str(owner_user.user_id),
                "business_id": str(owner_user.business_id),
                "email": owner_user.email,
                "role": owner_user.role,
                "full_name": owner_user.full_name,
            }
        )
        r = client.get(
            "/api/v1/marketing/cms/blog", headers={"Authorization": f"Bearer {tenant_token}"}
        )
        assert r.status_code == 401

    def test_platform_token_rejected_by_marketing_cms_endpoint(self, client, platform_admin):
        platform_token = create_platform_access_token(
            {
                "platform_admin_id": str(platform_admin.id),
                "email": platform_admin.email,
                "full_name": platform_admin.full_name,
                "platform_role": platform_admin.platform_role,
                "impersonation_allowed": platform_admin.impersonation_allowed,
                "phash": platform_admin.hashed_password[-8:],
            }
        )
        r = client.get(
            "/api/v1/marketing/cms/blog", headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert r.status_code == 401

    def test_expired_marketing_cms_token_rejected(self, client, marketing_cms_admin: MarketingCmsAdmin):
        token = create_marketing_cms_access_token(
            {
                "marketing_cms_admin_id": str(marketing_cms_admin.id),
                "email": marketing_cms_admin.email,
                "full_name": marketing_cms_admin.full_name,
            },
            expires_delta=timedelta(seconds=-1),
        )
        r = client.get(
            "/api/v1/marketing/cms/blog", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401

    def test_password_change_invalidates_outstanding_token(
        self, client, test_db, marketing_cms_admin: MarketingCmsAdmin
    ):
        token = create_marketing_cms_access_token(
            {
                "marketing_cms_admin_id": str(marketing_cms_admin.id),
                "email": marketing_cms_admin.email,
                "full_name": marketing_cms_admin.full_name,
                "phash": marketing_cms_admin.hashed_password[-8:],
            }
        )
        from app.core.security import hash_password

        marketing_cms_admin.hashed_password = hash_password("a-new-password")
        test_db.commit()

        r = client.get(
            "/api/v1/marketing/cms/blog", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401
