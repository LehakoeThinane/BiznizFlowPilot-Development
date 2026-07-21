"""Per-user email account service - self-service IMAP/SMTP connection,
inbox listing/reading, and send. Separate from the org-wide SMTP sender
in app/services/email.py (which is only for system-generated emails)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.integrations import imap_client
from app.integrations.imap_client import MessageDetail, MessageSummary
from app.models.user_email import UserEmailAccount
from app.repositories.user_email import UserEmailAccountRepository
from app.workflow_engine.email_provider import SMTPEmailProvider


class EmailAccountNotConfiguredError(Exception):
    """Raised when the caller has no (or an incomplete) connected mailbox."""


class UserEmailAccountService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserEmailAccountRepository(db)

    def get_account(self, business_id: UUID, user_id: UUID) -> UserEmailAccount | None:
        return self.repo.get_by_user_id(business_id, user_id)

    def set_account(
        self,
        business_id: UUID,
        user_id: UUID,
        imap_host: str,
        imap_port: int,
        imap_username: str,
        imap_password: str | None,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str | None,
        smtp_from_email: str,
        smtp_from_name: str,
    ) -> UserEmailAccount:
        """Create or update the caller's mailbox connection.

        imap_password/smtp_password = None means "leave the already-stored
        (encrypted) password unchanged" - mirrors OrganizationService.set_email_config.
        IMAP login validation happens in the API route, not here - this
        method's only job is persisting config.
        """
        account = self.get_account(business_id, user_id)

        fields = {
            "imap_host": imap_host,
            "imap_port": imap_port,
            "imap_username": imap_username,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_username": smtp_username,
            "smtp_from_email": smtp_from_email,
            "smtp_from_name": smtp_from_name,
        }
        if imap_password:
            fields["imap_password_encrypted"] = encrypt_secret(imap_password)
        if smtp_password:
            fields["smtp_password_encrypted"] = encrypt_secret(smtp_password)

        if account is None:
            account = self.repo.create(business_id=business_id, user_id=user_id, **fields)
        else:
            for key, value in fields.items():
                setattr(account, key, value)
            self.db.commit()
            self.db.refresh(account)

        return account

    def delete_account(self, business_id: UUID, user_id: UUID) -> bool:
        account = self.get_account(business_id, user_id)
        if not account:
            return False
        return self.repo.delete(business_id, account.id)

    def list_inbox(self, business_id: UUID, user_id: UUID, limit: int = 50, offset: int = 0) -> list[MessageSummary]:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        return imap_client.list_messages(account.imap_host, account.imap_port, account.imap_username, password, limit, offset)

    def get_message(self, business_id: UUID, user_id: UUID, uid: str) -> MessageDetail:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        return imap_client.get_message(account.imap_host, account.imap_port, account.imap_username, password, uid)

    def send_message(self, business_id: UUID, user_id: UUID, to: str, subject: str, body: str) -> None:
        account = self.get_account(business_id, user_id)
        if not account or not (
            account.smtp_host and account.smtp_username and account.smtp_password_encrypted and account.smtp_from_email
        ):
            raise EmailAccountNotConfiguredError("Connect your email account first.")

        password = decrypt_secret(account.smtp_password_encrypted)
        provider = SMTPEmailProvider(
            host=account.smtp_host,
            port=account.smtp_port,
            username=account.smtp_username,
            password=password,
            use_tls=(account.smtp_port != 465),
            use_ssl=(account.smtp_port == 465),
            default_from_email=account.smtp_from_email,
            default_from_name=account.smtp_from_name,
        )
        provider.send(recipient=to, subject=subject, body=body)

    def _require_account_with_imap(self, business_id: UUID, user_id: UUID) -> UserEmailAccount:
        account = self.get_account(business_id, user_id)
        if not account or not (account.imap_host and account.imap_username and account.imap_password_encrypted):
            raise EmailAccountNotConfiguredError("Connect your email account first.")
        return account
