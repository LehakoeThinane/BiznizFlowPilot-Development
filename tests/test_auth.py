"""Tests for authentication.

There is no public self-service registration endpoint - new client
organizations are provisioned by a platform admin, then the owner joins via
an invite (see app/api/platform_admin.py, app/services/invitation.py).
_create_user() below recreates just the end state these tests need (a real
owner user in the DB with known credentials) without going through that flow.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.services.auth import AuthService


def _create_user(test_db: Session, data: dict) -> User:
    organization = Organization(id=uuid4(), name=data["business_name"], billing_email=data["email"])
    test_db.add(organization)
    test_db.commit()

    business = Business(
        id=uuid4(), organization_id=organization.id, name=data["business_name"],
        email=data["email"], is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()

    user = User(
        id=uuid4(), business_id=business.id, email=data["email"],
        hashed_password=hash_password(data["password"]),
        first_name=data["first_name"], last_name=data["last_name"],
        role="owner", is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestLogin:
    """Test user login."""

    def test_login_success(self, client, test_db, sample_user_data):
        """Test successful login."""
        _create_user(test_db, sample_user_data)

        # Login
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"],
        }
        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_invalid_password(self, client, test_db, sample_user_data):
        """Test login with wrong password."""
        _create_user(test_db, sample_user_data)

        # Try login with wrong password
        login_data = {
            "email": sample_user_data["email"],
            "password": "wrongpassword",
        }
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_nonexistent_email(self, client):
        """Test login with non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123",
        }
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]


class TestPasswordReset:
    """Test password reset flow."""

    def test_password_reset_request_returns_token(self, client, test_db, sample_user_data):
        """Reset request returns a generic message (token delivered via email only)."""
        _create_user(test_db, sample_user_data)

        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": sample_user_data["email"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "sent" in data["message"].lower() or "reset" in data["message"].lower()

    def test_password_reset_confirm_updates_password(self, client, sample_user_data, test_db):
        """Confirm reset should invalidate old password and allow new one."""
        _create_user(test_db, sample_user_data)

        # Token is no longer returned in the API response (security: prevents enumeration).
        # Obtain it directly from the service layer as the email system would.
        token = AuthService(test_db).request_password_reset(email=sample_user_data["email"])

        confirm_response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "newpassword123"},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["message"] == "Password reset successful"

        old_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": sample_user_data["email"], "password": "newpassword123"},
        )
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()

    def test_password_reset_confirm_rejects_invalid_token(self, client):
        """Invalid reset token should be rejected."""
        response = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "not-a-valid-token", "new_password": "newpassword123"},
        )
        assert response.status_code == 400
        assert "Invalid or expired reset token" in response.json()["detail"]

    def test_password_reset_token_is_one_time_use(self, client, sample_user_data, test_db):
        """A reset token may only be used once; a second use must be rejected."""
        _create_user(test_db, sample_user_data)
        token = AuthService(test_db).request_password_reset(email=sample_user_data["email"])

        # First use — succeeds
        first = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "firstnewpass123"},
        )
        assert first.status_code == 200

        # Second use — phash fingerprint no longer matches; must be rejected
        second = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "secondnewpass456"},
        )
        assert second.status_code == 400
        assert "Invalid or expired reset token" in second.json()["detail"]

    def test_existing_access_token_rejected_after_password_reset(
        self, client, sample_user_data, test_db
    ):
        """Active access tokens must be invalidated when the password changes."""
        _create_user(test_db, sample_user_data)

        login_resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": sample_user_data["email"],
                "password": sample_user_data["password"],
            },
        )
        old_access_token = login_resp.json()["access_token"]

        # Verify the token works before the reset
        pre_reset = client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {old_access_token}"}
        )
        assert pre_reset.status_code == 200

        # Reset the password — phash in old token no longer matches DB
        token = AuthService(test_db).request_password_reset(email=sample_user_data["email"])
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "brandnewpass789"},
        )

        # Old access token must now be rejected
        post_reset = client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {old_access_token}"}
        )
        assert post_reset.status_code == 401
        assert "Session invalidated" in post_reset.json()["detail"]


class TestProtectedRoutes:
    """Test protected routes requiring authentication."""

    def test_get_current_user_with_token(self, client, registered_user):
        """Test accessing protected route with valid token."""
        access_token = registered_user["access_token"]
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "business_id" in data
        assert "email" in data

    def test_get_current_user_with_users_me_alias(self, client, registered_user):
        """Test compatibility alias route for current user."""
        access_token = registered_user["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "business_id" in data
        assert "email" in data

    def test_get_current_user_without_token(self, client):
        """Test accessing protected route without token."""
        response = client.get("/api/v1/me")
        
        assert response.status_code == 401
        assert "Missing or invalid authorization header" in response.json()["detail"]

    def test_get_current_user_invalid_token(self, client):
        """Test accessing protected route with invalid token."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.get("/api/v1/me", headers=headers)

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    def test_get_current_user_token_without_role_claim_uses_db_role(
        self, client, registered_user
    ):
        """Token without role claim should still resolve authoritative DB role."""
        access_token = registered_user["access_token"]
        base_headers = {"Authorization": f"Bearer {access_token}"}
        me_response = client.get("/api/v1/me", headers=base_headers)
        assert me_response.status_code == 200
        me_data = me_response.json()

        roleless_token = create_access_token(
            {
                "sub": me_data["user_id"],
                "user_id": me_data["user_id"],
                "business_id": me_data["business_id"],
                "email": me_data["email"],
                # intentionally omit role/full_name
            }
        )

        roleless_headers = {"Authorization": f"Bearer {roleless_token}"}
        roleless_response = client.get("/api/v1/me", headers=roleless_headers)

        assert roleless_response.status_code == 200
        roleless_data = roleless_response.json()
        assert roleless_data["role"] == "owner"


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health check (no auth required)."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
