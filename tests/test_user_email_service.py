"""Tests for app/services/user_email.py's UserEmailAccountService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.integrations.imap_client import FolderInfo
from app.models.business import Business
from app.models.organization import Organization
from app.services.user_email import EmailAccountNotConfiguredError, FolderNotFoundError, UserEmailAccountService


def _make_business(test_db: Session) -> Business:
    org = Organization(id=uuid4(), name="Test Org", billing_email=f"billing-{uuid4().hex[:8]}@example.com")
    test_db.add(org)
    test_db.commit()
    business = Business(
        id=uuid4(), organization_id=org.id, name="Test Business",
        email=f"biz-{uuid4().hex[:8]}@example.com", is_primary_subsidiary=True,
    )
    test_db.add(business)
    test_db.commit()
    return business


class TestSetAccount:
    def test_creates_new_account_with_encrypted_passwords(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)

        account = service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="imap-secret",
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password="smtp-secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )

        assert account.imap_password_encrypted != "imap-secret"
        assert decrypt_secret(account.imap_password_encrypted) == "imap-secret"
        assert decrypt_secret(account.smtp_password_encrypted) == "smtp-secret"

    def test_null_password_leaves_existing_password_unchanged(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="original-secret",
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password="smtp-secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )

        updated = service.set_account(
            business.id, user_id,
            imap_host="imap2.example.com", imap_port=993, imap_username="me@example.com",
            imap_password=None,
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password=None, smtp_from_email="me@example.com", smtp_from_name="Me",
        )

        assert updated.imap_host == "imap2.example.com"
        assert decrypt_secret(updated.imap_password_encrypted) == "original-secret"

    def test_get_account_returns_none_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        assert service.get_account(business.id, uuid4()) is None

    def test_delete_account(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password="secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )
        assert service.delete_account(business.id, user_id) is True
        assert service.get_account(business.id, user_id) is None
        assert service.delete_account(business.id, user_id) is False


class TestSendMessage:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.send_message(business.id, uuid4(), "to@example.com", "Subject", "Body")

    def test_sends_via_smtp_email_provider(self, test_db: Session, monkeypatch):
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

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password="smtp-secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )

        service.send_message(business.id, user_id, "to@example.com", "Hello", "Body text")

        assert len(_FakeSMTP.sent_messages) == 1
        sent = _FakeSMTP.sent_messages[0]
        assert "Cc" not in sent

    def test_cc_recipients_included_in_message(self, test_db: Session, monkeypatch):
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

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
            smtp_password="smtp-secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )

        service.send_message(
            business.id, user_id, "to@example.com", "Hello", "Body text",
            cc=["cc1@example.com", "cc2@example.com"],
        )

        assert len(_FakeSMTP.sent_messages) == 1
        sent = _FakeSMTP.sent_messages[0]
        assert sent["Cc"] == "cc1@example.com, cc2@example.com"
        sent = _FakeSMTP.sent_messages[0]
        assert sent["To"] == "to@example.com"
        assert sent["Subject"] == "Hello"

    def test_port_465_infers_implicit_ssl(self, test_db: Session, monkeypatch):
        captured = {}

        class _FakeSMTPSSL:
            def __init__(self, host, port, timeout=None):
                captured["ssl"] = True

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def ehlo(self):
                pass

            def login(self, username, password):
                pass

            def send_message(self, message):
                return {}

        monkeypatch.setattr("smtplib.SMTP_SSL", _FakeSMTPSSL)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        service.set_account(
            business.id, user_id,
            imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
            imap_password="secret",
            smtp_host="smtp.example.com", smtp_port=465, smtp_username="me@example.com",
            smtp_password="smtp-secret", smtp_from_email="me@example.com", smtp_from_name="Me",
        )
        service.send_message(business.id, user_id, "to@example.com", "Hello", "Body")
        assert captured.get("ssl") is True


def _connect_account(service: UserEmailAccountService, business_id, user_id) -> None:
    service.set_account(
        business_id, user_id,
        imap_host="imap.example.com", imap_port=993, imap_username="me@example.com",
        imap_password="secret",
        smtp_host="smtp.example.com", smtp_port=587, smtp_username="me@example.com",
        smtp_password="secret", smtp_from_email="me@example.com", smtp_from_name="Me",
    )


class TestListFolders:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.list_folders(business.id, uuid4())

    def test_delegates_to_imap_client(self, test_db: Session, monkeypatch):
        captured = {}

        def _fake_list_folders(host, port, username, password):
            captured["args"] = (host, port, username, password)
            return [FolderInfo(name="Sent", delimiter="/", attributes=["\\Sent"], role="sent")]

        monkeypatch.setattr("app.services.user_email.imap_client.list_folders", _fake_list_folders)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        folders = service.list_folders(business.id, user_id)
        assert folders[0].role == "sent"
        assert captured["args"][2] == "me@example.com"


class TestListInboxFolder:
    def test_inbox_and_starred_skip_folder_resolution(self, test_db: Session, monkeypatch):
        captured = {}

        def _fake_list_messages(host, port, username, password, limit, offset, folder, only_flagged):
            captured["folder"] = folder
            captured["only_flagged"] = only_flagged
            return []

        monkeypatch.setattr("app.services.user_email.imap_client.list_messages", _fake_list_messages)
        monkeypatch.setattr(
            "app.services.user_email.imap_client.list_folders",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not resolve folders for inbox/starred")),
        )

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        service.list_inbox(business.id, user_id, folder="starred")
        assert captured["folder"] == "INBOX"
        assert captured["only_flagged"] is True

    def test_other_folder_resolves_via_list_folders(self, test_db: Session, monkeypatch):
        monkeypatch.setattr(
            "app.services.user_email.imap_client.list_folders",
            lambda *a, **k: [FolderInfo(name="Sent Items", delimiter="/", attributes=[], role="sent")],
        )
        captured = {}

        def _fake_list_messages(host, port, username, password, limit, offset, folder, only_flagged):
            captured["folder"] = folder
            return []

        monkeypatch.setattr("app.services.user_email.imap_client.list_messages", _fake_list_messages)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        service.list_inbox(business.id, user_id, folder="sent")
        assert captured["folder"] == "Sent Items"

    def test_unresolvable_folder_raises(self, test_db: Session, monkeypatch):
        monkeypatch.setattr("app.services.user_email.imap_client.list_folders", lambda *a, **k: [])

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        with pytest.raises(FolderNotFoundError):
            service.list_inbox(business.id, user_id, folder="sent")


class TestSetMessageFlagsService:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.set_message_flags(business.id, uuid4(), "5", is_starred=True)

    def test_delegates_to_imap_client(self, test_db: Session, monkeypatch):
        captured = {}

        def _fake_set_flags(host, port, username, password, uid, folder, is_starred, is_read):
            captured.update(uid=uid, folder=folder, is_starred=is_starred, is_read=is_read)

        monkeypatch.setattr("app.services.user_email.imap_client.set_message_flags", _fake_set_flags)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        service.set_message_flags(business.id, user_id, "5", is_starred=True)
        assert captured == {"uid": "5", "folder": "INBOX", "is_starred": True, "is_read": None}


class TestArchiveMessageService:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.archive_message(business.id, uuid4(), "5")

    def test_delegates_to_imap_client(self, test_db: Session, monkeypatch):
        monkeypatch.setattr(
            "app.services.user_email.imap_client.archive_message",
            lambda host, port, username, password, uid, source_folder: "Archive",
        )

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        assert service.archive_message(business.id, user_id, "5") == "Archive"


class TestDeleteMessageService:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.delete_message(business.id, uuid4(), "5")

    def test_delegates_to_imap_client(self, test_db: Session, monkeypatch):
        captured = {}

        def _fake_delete(host, port, username, password, uid, source_folder):
            captured.update(uid=uid, source_folder=source_folder)

        monkeypatch.setattr("app.services.user_email.imap_client.delete_message", _fake_delete)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        service.delete_message(business.id, user_id, "5")
        assert captured == {"uid": "5", "source_folder": "INBOX"}


class TestGetAttachmentService:
    def test_raises_when_not_configured(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        with pytest.raises(EmailAccountNotConfiguredError):
            service.get_attachment(business.id, uuid4(), "5", 0)

    def test_delegates_to_imap_client(self, test_db: Session, monkeypatch):
        captured = {}

        def _fake_get_attachment(host, port, username, password, uid, attachment_index, folder):
            captured.update(uid=uid, attachment_index=attachment_index, folder=folder)
            return "note.txt", "text/plain", b"hello world"

        monkeypatch.setattr("app.services.user_email.imap_client.get_attachment_content", _fake_get_attachment)

        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        result = service.get_attachment(business.id, user_id, "5", 0)
        assert result == ("note.txt", "text/plain", b"hello world")
        assert captured == {"uid": "5", "attachment_index": 0, "folder": "INBOX"}


class TestDisplayPrefs:
    def test_get_returns_defaults_with_no_account_row(self, test_db: Session):
        business = _make_business(test_db)
        service = UserEmailAccountService(test_db)
        theme, background = service.get_display_prefs(business.id, uuid4())
        assert (theme, background) == ("dark", None)

    def test_set_creates_bare_prefs_only_row(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)

        theme, background = service.set_display_prefs(business.id, user_id, "light", "sunset")
        assert (theme, background) == ("light", "sunset")

        account = service.get_account(business.id, user_id)
        assert account is not None
        assert account.imap_host is None  # prefs-only row, no mailbox configured

    def test_set_on_configured_account_leaves_imap_fields_untouched(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)
        _connect_account(service, business.id, user_id)

        service.set_display_prefs(business.id, user_id, "light", None)

        account = service.get_account(business.id, user_id)
        assert account.email_theme == "light"
        assert account.email_background is None
        assert account.imap_host == "imap.example.com"

    def test_set_background_none_clears_it(self, test_db: Session):
        business = _make_business(test_db)
        user_id = uuid4()
        service = UserEmailAccountService(test_db)

        service.set_display_prefs(business.id, user_id, "dark", "sunset")
        theme, background = service.set_display_prefs(business.id, user_id, "dark", None)
        assert (theme, background) == ("dark", None)
