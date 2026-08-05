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
from app.workflow_engine.email_provider import EmailAttachment, SMTPEmailProvider


class EmailAccountNotConfiguredError(Exception):
    """Raised when the caller has no (or an incomplete) connected mailbox."""


class FolderNotFoundError(Exception):
    """Raised when a role key (sent/drafts/trash) can't be resolved to a
    real folder on the caller's mailbox."""


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

    def get_display_prefs(self, business_id: UUID, user_id: UUID) -> tuple[str, str | None]:
        """Email-page-scoped display prefs (theme, background) - independent
        of whether a mailbox is actually connected. Returns the default
        ("dark", None) if no account row exists at all yet."""
        account = self.get_account(business_id, user_id)
        if account is None:
            return "dark", None
        return account.email_theme, account.email_background

    def set_display_prefs(
        self, business_id: UUID, user_id: UUID, theme: str, background: str | None,
    ) -> tuple[str, str | None]:
        """Full-replace the display-pref columns - creates a bare prefs-only
        row if none exists yet, and never touches IMAP/SMTP fields on an
        existing row. background=None unambiguously means "no background"
        (this is PUT semantics, not a partial patch)."""
        account = self.get_account(business_id, user_id)
        if account is None:
            account = self.repo.create(
                business_id=business_id, user_id=user_id,
                email_theme=theme, email_background=background,
            )
        else:
            account.email_theme = theme
            account.email_background = background
            self.db.commit()
            self.db.refresh(account)
        return account.email_theme, account.email_background

    def list_folders(self, business_id: UUID, user_id: UUID) -> list[imap_client.FolderInfo]:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        return imap_client.list_folders(account.imap_host, account.imap_port, account.imap_username, password)

    def list_inbox(
        self, business_id: UUID, user_id: UUID, limit: int = 50, offset: int = 0, folder: str = "inbox"
    ) -> list[MessageSummary]:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        real_folder = "INBOX" if folder in ("inbox", "starred") else self._resolve_folder_name(business_id, user_id, folder)
        return imap_client.list_messages(
            account.imap_host, account.imap_port, account.imap_username, password,
            limit, offset, folder=real_folder, only_flagged=(folder == "starred"),
        )

    def get_message(self, business_id: UUID, user_id: UUID, uid: str, folder: str = "inbox") -> MessageDetail:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        real_folder = "INBOX" if folder in ("inbox", "starred") else self._resolve_folder_name(business_id, user_id, folder)
        return imap_client.get_message(
            account.imap_host, account.imap_port, account.imap_username, password, uid, folder=real_folder
        )

    def set_message_flags(
        self, business_id: UUID, user_id: UUID, uid: str, folder: str = "inbox",
        is_starred: bool | None = None, is_read: bool | None = None,
    ) -> None:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        real_folder = "INBOX" if folder in ("inbox", "starred") else self._resolve_folder_name(business_id, user_id, folder)
        imap_client.set_message_flags(
            account.imap_host, account.imap_port, account.imap_username, password, uid,
            folder=real_folder, is_starred=is_starred, is_read=is_read,
        )

    def archive_message(self, business_id: UUID, user_id: UUID, uid: str, folder: str = "inbox") -> str:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        real_folder = "INBOX" if folder in ("inbox", "starred") else self._resolve_folder_name(business_id, user_id, folder)
        return imap_client.archive_message(
            account.imap_host, account.imap_port, account.imap_username, password, uid, source_folder=real_folder
        )

    def delete_message(self, business_id: UUID, user_id: UUID, uid: str, folder: str = "inbox") -> None:
        account = self._require_account_with_imap(business_id, user_id)
        password = decrypt_secret(account.imap_password_encrypted)
        real_folder = "INBOX" if folder in ("inbox", "starred") else self._resolve_folder_name(business_id, user_id, folder)
        imap_client.delete_message(
            account.imap_host, account.imap_port, account.imap_username, password, uid, source_folder=real_folder
        )

    def _resolve_folder_name(self, business_id: UUID, user_id: UUID, role_key: str) -> str:
        """Map a role key (sent/drafts/trash/...) to this account's real
        IMAP mailbox name. inbox/starred are handled by callers directly
        (literal "INBOX", no round-trip needed) - this is only reached for
        the roles that require a folder listing."""
        folders = self.list_folders(business_id, user_id)
        match = next((f for f in folders if f.role == role_key), None)
        if match is None:
            raise FolderNotFoundError(f"No folder with role {role_key!r} found on this mailbox.")
        return match.name

    def send_message(
        self,
        business_id: UUID,
        user_id: UUID,
        to: str,
        subject: str,
        body: str,
        attachments: list[EmailAttachment] | None = None,
    ) -> None:
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
        provider.send(recipient=to, subject=subject, body=body, attachments=attachments)

    def _require_account_with_imap(self, business_id: UUID, user_id: UUID) -> UserEmailAccount:
        account = self.get_account(business_id, user_id)
        if not account or not (account.imap_host and account.imap_username and account.imap_password_encrypted):
            raise EmailAccountNotConfiguredError("Connect your email account first.")
        return account
