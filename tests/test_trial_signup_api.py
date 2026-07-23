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
from app.repositories.user import UserRepository


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

        # Seed data landed, scoped to this new business only - sized to look
        # like an established ~75-person company, not a 3-person demo.
        assert test_db.query(Department).filter(Department.business_id == user.business_id).count() == 9
        assert test_db.query(Employee).filter(Employee.business_id == user.business_id).count() == 75
        assert test_db.query(Lead).filter(Lead.business_id == user.business_id).count() == 30
        assert test_db.query(Product).filter(Product.business_id == user.business_id).count() == 26
        assert test_db.query(PayrollPeriod).filter(PayrollPeriod.business_id == user.business_id).count() == 3
        assert test_db.query(Payslip).filter(Payslip.business_id == user.business_id).count() == 144
        assert test_db.query(LeaveRequest).filter(LeaveRequest.business_id == user.business_id).count() == 25
        assert test_db.query(Meeting).filter(Meeting.business_id == user.business_id).count() == 8
        assert test_db.query(Document).filter(Document.business_id == user.business_id).count() == 18

        # A handful of "colleague" users exist purely for Messages/Meetings
        # realism (Operations, Sales, Finance, Warehouse managers) - none of
        # them are actually loggable-in, same trick as a Google-only account.
        colleagues = test_db.query(User).filter(User.business_id == user.business_id, User.id != user.id).all()
        assert len(colleagues) == 4
        assert all(c.role == "manager" for c in colleagues)

        conversations = test_db.query(Conversation).filter(Conversation.business_id == user.business_id).all()
        assert len(conversations) == 5  # 3x 1:1 + Naledi's 1:1 + one small-group thread
        total_messages = sum(
            test_db.query(Message).filter(Message.conversation_id == c.id).count() for c in conversations
        )
        assert total_messages == 26

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
        assert leads_a == 30
        assert leads_b == 30


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

    def test_concurrent_google_signup_recovers_instead_of_crashing(self, client, test_db: Session):
        """Two near-simultaneous requests for the same Google account (e.g. a
        double-click) can both pass the "does this account already exist?"
        check before either commits - the loser used to crash with a raw
        IntegrityError on the google_sub unique constraint instead of just
        logging the user into the account the winner had already created."""
        with patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify:
            mock_verify.return_value = self._mock_payload(sub="race-sub-1", email="race@example.com")
            r1 = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Race Co", "credential": "fake-id-token"},
            )
        assert r1.status_code == 200
        first_business_id = test_db.query(User).filter(User.google_sub == "race-sub-1").first().business_id

        # Force the pre-insert existence check to miss on its first call only
        # (simulating the race), then fall through to the real lookup on the
        # recovery path inside the except block.
        real_get_by_google_sub = UserRepository.get_by_google_sub
        calls = {"n": 0}

        def flaky_get_by_google_sub(self, google_sub):
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return real_get_by_google_sub(self, google_sub)

        with (
            patch("app.services.trial_signup.google_id_token.verify_oauth2_token") as mock_verify,
            patch.object(UserRepository, "get_by_google_sub", flaky_get_by_google_sub),
            # In a real race the concurrent (not-yet-committed) row is also
            # invisible to this email check, not just the google_sub one.
            patch.object(UserRepository, "get_by_email_all", return_value=None),
        ):
            mock_verify.return_value = self._mock_payload(sub="race-sub-1", email="race@example.com")
            r2 = client.post(
                "/api/v1/signup/trial/google",
                json={"organization_name": "Race Co Again", "credential": "fake-id-token"},
            )

        assert r2.status_code == 200
        assert r2.json()["access_token"]

        users = test_db.query(User).filter(User.google_sub == "race-sub-1").all()
        assert len(users) == 1
        assert users[0].business_id == first_business_id
