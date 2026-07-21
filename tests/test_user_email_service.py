"""Tests for app/services/user_email.py's UserEmailAccountService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.models.business import Business
from app.models.organization import Organization
from app.services.user_email import EmailAccountNotConfiguredError, UserEmailAccountService


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
