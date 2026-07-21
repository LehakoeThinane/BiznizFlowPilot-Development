"""API tests for the public free-trial signup flow (email/password + Google)."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.hr import Department, Employee, LeaveRequest, PayrollPeriod, Payslip
from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.messaging import Conversation, Message
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User


def _password_signup_body(email: str = "founder@example.com", org: str = "Founder Co") -> dict:
    return {
        "organization_name": org,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": email,
        "password": "correct-horse-battery",
    }


class TestPasswordSignup:
    def test_creates_org_business_owner_and_seeds_sample_data(self, client, test_db: Session):
        r = client.post("/api/v1/signup/trial", json=_password_signup_body())
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

        user = test_db.query(User).filter(User.email == "founder@example.com").first()
        assert user is not None
        assert user.role == "owner"
        assert user.auth_provider == "password"
        assert user.google_sub is None

        org = test_db.query(Organization).filter(Organization.id == user.business.organization_id).first()
        assert org.plan_tier == "trial"
        assert org.trial_ends_at is not None

        # Seed data landed, scoped to this new business only.
        assert test_db.query(Department).filter(Department.business_id == user.business_id).count() == 1
        assert test_db.query(Employee).filter(Employee.business_id == user.business_id).count() == 3
        assert test_db.query(Lead).filter(Lead.business_id == user.business_id).count() == 4
        assert test_db.query(Product).filter(Product.business_id == user.business_id).count() == 4
        assert test_db.query(PayrollPeriod).filter(PayrollPeriod.business_id == user.business_id).count() == 1
        assert test_db.query(Payslip).filter(Payslip.business_id == user.business_id).count() == 3
        assert test_db.query(LeaveRequest).filter(LeaveRequest.business_id == user.business_id).count() == 2
        assert test_db.query(Meeting).filter(Meeting.business_id == user.business_id).count() == 1
        assert test_db.query(Document).filter(Document.business_id == user.business_id).count() == 1

        # A second "colleague" user exists purely for Messages/Meetings realism.
        colleague = (
            test_db.query(User)
            .filter(User.business_id == user.business_id, User.id != user.id)
            .first()
        )
        assert colleague is not None
        assert colleague.role == "manager"

        conversation = test_db.query(Conversation).filter(Conversation.business_id == user.business_id).first()
        assert conversation is not None
        assert test_db.query(Message).filter(Message.conversation_id == conversation.id).count() == 3

    def test_duplicate_email_rejected(self, client, test_db: Session):
        r1 = client.post("/api/v1/signup/trial", json=_password_signup_body())
        assert r1.status_code == 200

        r2 = client.post("/api/v1/signup/trial", json=_password_signup_body())
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"]

    def test_short_password_rejected(self, client):
        body = _password_signup_body()
        body["password"] = "short"
        r = client.post("/api/v1/signup/trial", json=body)
        assert r.status_code == 422

    def test_two_signups_get_isolated_seed_data(self, client, test_db: Session):
        """Two different trial signups must never see each other's seeded rows -
        the same business_id isolation every other tenant already relies on."""
        r1 = client.post("/api/v1/signup/trial", json=_password_signup_body(email="a@example.com", org="A Co"))
        r2 = client.post("/api/v1/signup/trial", json=_password_signup_body(email="b@example.com", org="B Co"))
        assert r1.status_code == 200
        assert r2.status_code == 200

        user_a = test_db.query(User).filter(User.email == "a@example.com").first()
        user_b = test_db.query(User).filter(User.email == "b@example.com").first()
        assert user_a.business_id != user_b.business_id

        leads_a = test_db.query(Lead).filter(Lead.business_id == user_a.business_id).count()
        leads_b = test_db.query(Lead).filter(Lead.business_id == user_b.business_id).count()
        assert leads_a == 4
        assert leads_b == 4


class TestGoogleSignup:
    def _mock_payload(self, sub="google-sub-123", email="visitor@example.com", email_verified=True):
        return {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "given_name": "Grace",
            "family_name": "Hopper",
        }

    def test_creates_new_trial_account(self, client, test_db: Session):
        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = self._mock_payload()
            r = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Hopper Co", "credential": "fake-id-token"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["access_token"]

        user = test_db.query(User).filter(User.email == "visitor@example.com").first()
        assert user is not None
        assert user.auth_provider == "google"
        assert user.google_sub == "google-sub-123"
        assert user.role == "owner"

    def test_returning_google_user_logs_in_without_duplicate_org(self, client, test_db: Session):
        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = self._mock_payload()
            r1 = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Hopper Co", "credential": "fake-id-token"},
            )
            assert r1.status_code == 200

            r2 = client.post(
                "/api/v1/signup/trial/google",
                # Different org name on the second call - must be ignored, since
                # this is a returning user logging back in, not a new signup.
                json={"organization_name": "Some Other Name", "credential": "fake-id-token"},
            )
            assert r2.status_code == 200

        users = test_db.query(User).filter(User.google_sub == "google-sub-123").all()
        assert len(users) == 1

    def test_unverified_email_rejected(self, client):
        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = self._mock_payload(email_verified=False)
            r = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Hopper Co", "credential": "fake-id-token"},
            )
        assert r.status_code == 409

    def test_invalid_token_rejected(self, client):
        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.side_effect = ValueError("Token expired")
            r = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Hopper Co", "credential": "bad-token"},
            )
        assert r.status_code == 409

    def test_email_already_used_by_password_account_rejected(self, client, test_db: Session):
        r1 = client.post(
            "/api/v1/signup/trial",
            json=_password_signup_body(email="shared@example.com", org="Password Co"),
        )
        assert r1.status_code == 200

        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = self._mock_payload(sub="new-sub", email="shared@example.com")
            r2 = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Google Co", "credential": "fake-id-token"},
            )
        assert r2.status_code == 409
