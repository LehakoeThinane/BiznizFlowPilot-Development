"""API tests for app/api/user_email.py - the self-service per-user email
account/inbox/send endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.core.security import create_access_token
from app.integrations.imap_client import ImapAuthenticationError, ImapConnectionError, MessageDetail, MessageSummary
from app.models.user_email import UserEmailAccount
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


def _connect_body(**overrides) -> dict:
    body = {
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_username": "me@example.com",
        "imap_password": "imap-secret",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "me@example.com",
        "smtp_password": "smtp-secret",
        "smtp_from_email": "me@example.com",
        "smtp_from_name": "Me",
    }
    body.update(overrides)
    return body


class TestAuthAndTierGating:
    def test_requires_auth(self, client):
        r = client.get("/api/v1/email-account")
        assert r.status_code == 401

    def test_403_for_org_without_email_feature_tier(self, client, owner_user, owner_organization, test_db: Session):
        owner_organization.plan_tier = "starter"
        test_db.commit()
        r = client.get("/api/v1/email-account", headers=_auth_headers(owner_user))
        assert r.status_code == 403


class TestGetAndDeleteAccount:
    def test_get_when_not_configured_returns_200_all_null(self, client, owner_user):
        r = client.get("/api/v1/email-account", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        body = r.json()
        assert body["imap_host"] is None
        assert body["imap_password_set"] is False

    def test_delete_is_idempotent_when_nothing_configured(self, client, owner_user):
        r = client.delete("/api/v1/email-account", headers=_auth_headers(owner_user))
        assert r.status_code == 204


class TestSetAccount:
    def test_connect_requires_imap_password_on_first_setup(self, client, owner_user):
        r = client.put(
            "/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body(imap_password=None),
        )
        assert r.status_code == 400

    def test_connect_success_never_echoes_password(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        r = client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())
        assert r.status_code == 200
        body = r.json()
        assert body["imap_password_set"] is True
        assert body["smtp_password_set"] is True
        assert "imap_password" not in body
        assert "smtp_password" not in body

    def test_connect_maps_authentication_error_to_400_and_persists_nothing(self, client, owner_user, monkeypatch):
        def _raise(*args, **kwargs):
            raise ImapAuthenticationError("bad creds")

        monkeypatch.setattr("app.api.user_email.imap_client.list_messages", _raise)
        r = client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())
        assert r.status_code == 400

        get_r = client.get("/api/v1/email-account", headers=_auth_headers(owner_user))
        assert get_r.json()["imap_host"] is None

    def test_connect_maps_connection_error_to_400(self, client, owner_user, monkeypatch):
        def _raise(*args, **kwargs):
            raise ImapConnectionError("could not connect")

        monkeypatch.setattr("app.api.user_email.imap_client.list_messages", _raise)
        r = client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())
        assert r.status_code == 400

    def test_update_with_null_password_keeps_existing_password_valid(
        self, client, owner_user, owner_business, test_db: Session, monkeypatch
    ):
        business_id = owner_business.id  # capture before any request closes/detaches the shared test session
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        r2 = client.put(
            "/api/v1/email-account", headers=_auth_headers(owner_user),
            json=_connect_body(imap_password=None, smtp_password=None, imap_host="imap2.example.com"),
        )
        assert r2.status_code == 200
        assert r2.json()["imap_host"] == "imap2.example.com"

        account = (
            test_db.query(UserEmailAccount)
            .filter(UserEmailAccount.business_id == business_id)
            .first()
        )
        assert decrypt_secret(account.imap_password_encrypted) == "imap-secret"


class TestMessages:
    def test_list_requires_configured_account(self, client, owner_user):
        r = client.get("/api/v1/email-account/messages", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_list_happy_path(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        monkeypatch.setattr(
            "app.services.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit, offset: [
                MessageSummary(uid="1", from_address="a@example.com", subject="Hi", date=None, is_read=False),
            ],
        )
        r = client.get("/api/v1/email-account/messages", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["items"][0]["uid"] == "1"

    def test_get_message_happy_path(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        monkeypatch.setattr(
            "app.services.user_email.imap_client.get_message",
            lambda host, port, username, password, uid: MessageDetail(
                uid=uid, from_address="a@example.com", to_address="me@example.com",
                subject="Hi", date=None, body_html=None, body_text="Body",
            ),
        )
        r = client.get("/api/v1/email-account/messages/1", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["body_text"] == "Body"


class TestSend:
    def test_send_requires_configured_account(self, client, owner_user):
        r = client.post(
            "/api/v1/email-account/send", headers=_auth_headers(owner_user),
            json={"to": "to@example.com", "subject": "Hi", "body": "Body"},
        )
        assert r.status_code == 404

    def test_send_happy_path(self, client, owner_user, monkeypatch):
        class _FakeSMTP:
            sent_messages: list = []

            def __init__(self, host, port, timeout=None):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def ehlo(self):
                pass

            def starttls(self, context=None):
                pass

            def login(self, username, password):
                pass

            def send_message(self, message):
                _FakeSMTP.sent_messages.append(message)
                return {}

        monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        r = client.post(
            "/api/v1/email-account/send", headers=_auth_headers(owner_user),
            json={"to": "to@example.com", "subject": "Hi", "body": "Body"},
        )
        assert r.status_code == 200
        assert r.json()["sent"] is True
        assert len(_FakeSMTP.sent_messages) == 1
