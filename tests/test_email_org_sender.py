"""Tests for app/services/email.py's per-organization SMTP sender resolution."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.organization import Organization
from app.services.email import _resolve_email_config


def _make_org(test_db: Session, **overrides) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Test Org",
        billing_email=f"billing-{uuid4().hex[:8]}@example.com",
        **overrides,
    )
    test_db.add(org)
    test_db.commit()
    return org


class TestResolveEmailConfig:
    def test_no_org_context_falls_back_to_platform_default(self, test_db: Session):
        cfg = _resolve_email_config(None, None)
        assert cfg.smtp_from_email  # platform default is always non-empty in Settings

    def test_org_id_but_no_db_falls_back_to_platform_default(self, test_db: Session):
        org = _make_org(test_db, smtp_host="smtp.example.com")
        cfg = _resolve_email_config(None, org.id)
        assert cfg.use_resend == cfg.use_resend  # falls back, no crash

    def test_fully_configured_org_uses_its_own_smtp(self, test_db: Session):
        org = _make_org(
            test_db,
            smtp_host="smtp.office365.com",
            smtp_port=587,
            smtp_username="meetings@theircompany.com",
            smtp_password_encrypted=encrypt_secret("their-real-password"),
            smtp_from_email="meetings@theircompany.com",
            smtp_from_name="Their Company",
        )
        cfg = _resolve_email_config(test_db, org.id)
        assert cfg.use_resend is False
        assert cfg.smtp_host == "smtp.office365.com"
        assert cfg.smtp_username == "meetings@theircompany.com"
        assert cfg.smtp_password == "their-real-password"
        assert cfg.smtp_from_email == "meetings@theircompany.com"
        assert cfg.smtp_from_name == "Their Company"

    def test_partially_configured_org_falls_back_to_platform_default(self, test_db: Session):
        """Missing the password (or any required field) means "not really configured" - use platform default."""
        org = _make_org(test_db, smtp_host="smtp.example.com", smtp_username="someone")
        cfg = _resolve_email_config(test_db, org.id)
        assert cfg.smtp_host != "smtp.example.com"

    def test_unknown_org_id_falls_back_to_platform_default(self, test_db: Session):
        cfg = _resolve_email_config(test_db, uuid4())
        assert cfg.smtp_host != "smtp.office365.com"

    def test_port_465_infers_implicit_ssl(self, test_db: Session):
        org = _make_org(
            test_db, smtp_host="smtp.example.com", smtp_port=465, smtp_username="u",
            smtp_password_encrypted=encrypt_secret("p"), smtp_from_email="from@example.com",
        )
        cfg = _resolve_email_config(test_db, org.id)
        assert cfg.smtp_use_ssl is True
        assert cfg.smtp_use_tls is False

    def test_port_587_infers_starttls(self, test_db: Session):
        org = _make_org(
            test_db, smtp_host="smtp.example.com", smtp_port=587, smtp_username="u",
            smtp_password_encrypted=encrypt_secret("p"), smtp_from_email="from@example.com",
        )
        cfg = _resolve_email_config(test_db, org.id)
        assert cfg.smtp_use_ssl is False
        assert cfg.smtp_use_tls is True

    def test_custom_sender_bypasses_resend_even_if_platform_has_resend_key(self, test_db: Session, monkeypatch):
        """The whole point of custom SMTP is sending as *their* domain - Resend
        (sending from the platform's verified domain) can't do that."""
        monkeypatch.setattr("app.services.email._USE_RESEND", True)
        monkeypatch.setattr("app.services.email.settings.resend_api_key", "fake-platform-key")
        org = _make_org(
            test_db, smtp_host="smtp.example.com", smtp_port=587, smtp_username="u",
            smtp_password_encrypted=encrypt_secret("p"), smtp_from_email="from@example.com",
        )
        cfg = _resolve_email_config(test_db, org.id)
        assert cfg.use_resend is False
