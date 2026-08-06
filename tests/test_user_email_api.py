"""API tests for app/api/user_email.py - the self-service per-user email
account/inbox/send endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.core.security import create_access_token
from app.integrations.imap_client import (
    AttachmentNotFoundError,
    FolderInfo,
    ImapAuthenticationError,
    ImapConnectionError,
    MessageDetail,
    MessageSummary,
    NoArchiveFolderError,
)
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
            lambda host, port, username, password, limit, offset, folder, only_flagged: [
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
            lambda host, port, username, password, uid, folder: MessageDetail(
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
            data={"to": "to@example.com", "subject": "Hi", "body": "Body"},
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
            data={"to": "to@example.com", "subject": "Hi", "body": "Body"},
        )
        assert r.status_code == 200
        assert r.json()["sent"] is True
        assert len(_FakeSMTP.sent_messages) == 1

    def test_send_with_attachment(self, client, owner_user, monkeypatch):
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
            data={"to": "to@example.com", "subject": "Hi", "body": "Body"},
            files={"attachments": ("note.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 200
        sent = _FakeSMTP.sent_messages[0]
        assert sent.is_multipart()
        filenames = [part.get_filename() for part in sent.walk() if part.get_filename()]
        assert "note.txt" in filenames

    def test_send_rejects_oversized_attachment(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        oversized = b"x" * (20 * 1024 * 1024 + 1)
        r = client.post(
            "/api/v1/email-account/send", headers=_auth_headers(owner_user),
            data={"to": "to@example.com", "subject": "Hi", "body": "Body"},
            files={"attachments": ("big.bin", oversized, "application/octet-stream")},
        )
        assert r.status_code == 400

    def test_send_with_cc(self, client, owner_user, monkeypatch):
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
            data={"to": "to@example.com", "subject": "Hi", "body": "Body", "cc": ["cc@example.com"]},
        )
        assert r.status_code == 200
        assert _FakeSMTP.sent_messages[0]["Cc"] == "cc@example.com"


class TestDownloadAttachment:
    def test_requires_configured_account(self, client, owner_user):
        r = client.get("/api/v1/email-account/messages/1/attachments/0/download", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_happy_path(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        monkeypatch.setattr(
            "app.services.user_email.imap_client.get_attachment_content",
            lambda host, port, username, password, uid, attachment_index, folder: ("note.txt", "text/plain", b"hello world"),
        )
        r = client.get("/api/v1/email-account/messages/1/attachments/0/download", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.content == b"hello world"
        assert 'filename="note.txt"' in r.headers["content-disposition"]

    def test_missing_attachment_returns_404(self, client, owner_user, monkeypatch):
        monkeypatch.setattr(
            "app.api.user_email.imap_client.list_messages",
            lambda host, port, username, password, limit=1: [],
        )
        client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())

        def _raise(*args, **kwargs):
            raise AttachmentNotFoundError("No attachment at index 3 on message '1'.")

        monkeypatch.setattr("app.services.user_email.imap_client.get_attachment_content", _raise)
        r = client.get("/api/v1/email-account/messages/1/attachments/3/download", headers=_auth_headers(owner_user))
        assert r.status_code == 404


def _connect(client, owner_user, monkeypatch):
    monkeypatch.setattr(
        "app.api.user_email.imap_client.list_messages",
        lambda host, port, username, password, limit=1: [],
    )
    client.put("/api/v1/email-account", headers=_auth_headers(owner_user), json=_connect_body())


class TestFolders:
    def test_requires_configured_account(self, client, owner_user):
        r = client.get("/api/v1/email-account/folders", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_happy_path(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        monkeypatch.setattr(
            "app.services.user_email.imap_client.list_folders",
            lambda host, port, username, password: [
                FolderInfo(name="INBOX", delimiter="/", attributes=[], role="inbox"),
                FolderInfo(name="Sent", delimiter="/", attributes=["\\Sent"], role="sent"),
            ],
        )
        r = client.get("/api/v1/email-account/folders", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        items = r.json()["items"]
        assert {"name": "Sent", "role": "sent"} in items


class TestMessageFlags:
    def test_requires_configured_account(self, client, owner_user):
        r = client.patch(
            "/api/v1/email-account/messages/1/flags", headers=_auth_headers(owner_user), json={"is_starred": True},
        )
        assert r.status_code == 404

    def test_rejects_body_with_no_flags(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        r = client.patch(
            "/api/v1/email-account/messages/1/flags", headers=_auth_headers(owner_user), json={},
        )
        assert r.status_code == 422

    def test_star_only(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        captured = {}
        monkeypatch.setattr(
            "app.services.user_email.imap_client.set_message_flags",
            lambda host, port, username, password, uid, folder, is_starred, is_read: captured.update(
                is_starred=is_starred, is_read=is_read
            ),
        )
        r = client.patch(
            "/api/v1/email-account/messages/1/flags", headers=_auth_headers(owner_user), json={"is_starred": True},
        )
        assert r.status_code == 200
        assert captured == {"is_starred": True, "is_read": None}

    def test_both_flags(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        captured = {}
        monkeypatch.setattr(
            "app.services.user_email.imap_client.set_message_flags",
            lambda host, port, username, password, uid, folder, is_starred, is_read: captured.update(
                is_starred=is_starred, is_read=is_read
            ),
        )
        r = client.patch(
            "/api/v1/email-account/messages/1/flags", headers=_auth_headers(owner_user),
            json={"is_starred": False, "is_read": True},
        )
        assert r.status_code == 200
        assert captured == {"is_starred": False, "is_read": True}


class TestArchiveAndDelete:
    def test_archive_requires_configured_account(self, client, owner_user):
        r = client.post("/api/v1/email-account/messages/1/archive", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_archive_happy_path(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        monkeypatch.setattr(
            "app.services.user_email.imap_client.archive_message",
            lambda host, port, username, password, uid, source_folder: "Archive",
        )
        r = client.post("/api/v1/email-account/messages/1/archive", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json() == {"archived": True, "folder": "Archive"}

    def test_archive_no_archive_folder_is_404(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)

        def _raise(*args, **kwargs):
            raise NoArchiveFolderError("No Archive folder found on this mailbox.")

        monkeypatch.setattr("app.services.user_email.imap_client.archive_message", _raise)
        r = client.post("/api/v1/email-account/messages/1/archive", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_delete_requires_configured_account(self, client, owner_user):
        r = client.delete("/api/v1/email-account/messages/1", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_delete_happy_path(self, client, owner_user, monkeypatch):
        _connect(client, owner_user, monkeypatch)
        monkeypatch.setattr(
            "app.services.user_email.imap_client.delete_message",
            lambda host, port, username, password, uid, source_folder: None,
        )
        r = client.delete("/api/v1/email-account/messages/1", headers=_auth_headers(owner_user))
        assert r.status_code == 204


class TestDisplayPrefs:
    def test_get_returns_defaults_before_connecting(self, client, owner_user):
        r = client.get("/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json() == {"theme": "dark", "background": None}

    def test_put_succeeds_without_any_mailbox_configured(self, client, owner_user):
        r = client.put(
            "/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user),
            json={"theme": "light", "background": "sunset"},
        )
        assert r.status_code == 200
        assert r.json() == {"theme": "light", "background": "sunset"}

        get_r = client.get("/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user))
        assert get_r.json() == {"theme": "light", "background": "sunset"}

    def test_put_rejects_invalid_theme(self, client, owner_user):
        r = client.put(
            "/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user),
            json={"theme": "blue", "background": None},
        )
        assert r.status_code == 422

    def test_put_null_background_clears_it(self, client, owner_user):
        client.put(
            "/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user),
            json={"theme": "light", "background": "sunset"},
        )
        r = client.put(
            "/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user),
            json={"theme": "light", "background": None},
        )
        assert r.status_code == 200
        assert r.json()["background"] is None

    def test_prefs_survive_connecting_a_mailbox(self, client, owner_user, monkeypatch):
        client.put(
            "/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user),
            json={"theme": "light", "background": "sunset"},
        )
        _connect(client, owner_user, monkeypatch)

        r = client.get("/api/v1/email-account/display-prefs", headers=_auth_headers(owner_user))
        assert r.json() == {"theme": "light", "background": "sunset"}
