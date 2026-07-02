"""Tests for authentication."""

import pytest
from app.core.security import create_access_token
from app.services.auth import AuthService


class TestRegistration:
    """Test user registration."""

    def test_register_success(self, client, sample_user_data):
        """Test successful registration."""
        response = client.post("/api/v1/auth/register", json=sample_user_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 24 * 60 * 60

    def test_register_duplicate_email(self, client, sample_user_data):
        """Test registration with duplicate email fails."""
        # Register first user
        response1 = client.post("/api/v1/auth/register", json=sample_user_data)
        assert response1.status_code == 200
        
        # Try to register with same email
        response2 = client.post("/api/v1/auth/register", json=sample_user_data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    def test_register_missing_required_fields(self, client):
        """Test registration with missing fields."""
        incomplete_data = {
            "business_name": "Test",
            "email": "test@example.com",
            # Missing other required fields
        }
        
        response = client.post("/api/v1/auth/register", json=incomplete_data)
        assert response.status_code == 422  # Validation error


class TestLogin:
    """Test user login."""

    def test_login_success(self, client, sample_user_data):
        """Test successful login."""
        # Register user
        client.post("/api/v1/auth/register", json=sample_user_data)
        
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

    def test_login_invalid_password(self, client, sample_user_data):
        """Test login with wrong password."""
        # Register user
        client.post("/api/v1/auth/register", json=sample_user_data)
        
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

    def test_password_reset_request_returns_token(self, client, sample_user_data):
        """Reset request returns a generic message (token delivered via email only)."""
        client.post("/api/v1/auth/register", json=sample_user_data)

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
        client.post("/api/v1/auth/register", json=sample_user_data)

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
        client.post("/api/v1/auth/register", json=sample_user_data)
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
        client.post("/api/v1/auth/register", json=sample_user_data)

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
