"""Email provider abstraction and SMTP implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from functools import lru_cache
import smtplib
import socket
import ssl
from typing import Any

from app.core.config import settings


@dataclass(slots=True)
class EmailSendResult:
    """Result returned by an email provider after accepted send."""

    provider: str
    recipient: str
    subject: str
    message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EmailProviderError(Exception):
    """Base exception for provider send failures."""

    def __init__(self, message: str, *, metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.metadata = metadata or {}


class RetryableEmailProviderError(EmailProviderError):
    """Provider failure that should be retried."""


class TerminalEmailProviderError(EmailProviderError):
    """Provider failure that should not be retried."""


class EmailProvider(ABC):
    """Abstract email provider contract."""

    name: str

    @abstractmethod
    def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        from_email: str | None = None,
        from_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> EmailSendResult:
        """Send one email and return provider acceptance details."""


class SMTPEmailProvider(EmailProvider):
    """SMTP provider adapter used for Phase 5 notifications."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        use_ssl: bool = False,
        default_from_email: str | None = None,
        default_from_name: str | None = None,
        default_timeout_seconds: int = 10,
    ):
        if use_tls and use_ssl:
            raise ValueError("SMTP provider cannot enable both TLS and SSL simultaneously")

        self.host = host
        self.port = int(port)
        self.username = username or None
        self.password = password or None
        self.use_tls = bool(use_tls)
        self.use_ssl = bool(use_ssl)
        self.default_from_email = default_from_email
        self.default_from_name = default_from_name
        self.default_timeout_seconds = int(default_timeout_seconds)

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        from_email: str | None = None,
        from_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> EmailSendResult:
        timeout = int(timeout_seconds or self.default_timeout_seconds)
        sender_email = (from_email or self.default_from_email or "").strip()
        sender_name = (from_name or self.default_from_name or "").strip()
        if not sender_email:
            raise TerminalEmailProviderError("Missing sender email configuration")

        from_header = formataddr((sender_name, sender_email)) if sender_name else sender_email
        message = EmailMessage()
        message["From"] = from_header
        message["To"] = recipient
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=sender_email.split("@")[-1])
        message.set_content(body)

        request_metadata = {
            "host": self.host,
            "port": self.port,
            "timeout_seconds": timeout,
            **(metadata or {}),
        }

        try:
            if self.use_ssl:
                smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=timeout)
            else:
                smtp = smtplib.SMTP(self.host, self.port, timeout=timeout)

            with smtp:
                smtp.ehlo()
                if self.use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if self.username:
                    smtp.login(self.username, self.password or "")

                refused = smtp.send_message(message)
                if refused:
                    first_error = next(iter(refused.values()))
                    code = int(first_error[0]) if first_error else 550
                    msg = str(first_error[1]) if len(first_error) > 1 else "recipient refused"
                    retryable_codes = {421, 450}
                    if code in retryable_codes:
                        raise RetryableEmailProviderError(
                            f"Recipient temporarily refused ({code}): {msg}",
                            metadata=request_metadata,
                        )
                    raise TerminalEmailProviderError(
                        f"Recipient rejected ({code}): {msg}",
                        metadata=request_metadata,
                    )

            return EmailSendResult(
                provider=self.name,
                recipient=recipient,
                subject=subject,
                message_id=str(message["Message-ID"]),
                metadata=request_metadata,
            )
        except (socket.timeout, TimeoutError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as exc:
            raise RetryableEmailProviderError(
                f"SMTP transport timeout/disconnect: {exc}",
                metadata=request_metadata,
            ) from exc
        except smtplib.SMTPAuthenticationError as exc:
            raise TerminalEmailProviderError(
                f"SMTP authentication failed ({exc.smtp_code}): {exc.smtp_error}",
                metadata=request_metadata,
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise TerminalEmailProviderError(
                f"SMTP recipients refused: {exc.recipients}",
                metadata=request_metadata,
            ) from exc
        except smtplib.SMTPSenderRefused as exc:
            raise TerminalEmailProviderError(
                f"SMTP sender refused ({exc.smtp_code}): {exc.smtp_error}",
                metadata=request_metadata,
            ) from exc
        except smtplib.SMTPResponseException as exc:
            code = int(exc.smtp_code)
            message_text = exc.smtp_error.decode() if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
            retryable_codes = {421, 450}
            if code in retryable_codes:
                error_cls: type[EmailProviderError] = RetryableEmailProviderError
            else:
                error_cls = TerminalEmailProviderError
            raise error_cls(
                f"SMTP response error ({code}): {message_text}",
                metadata=request_metadata,
            ) from exc
        except OSError as exc:
            raise RetryableEmailProviderError(
                f"SMTP network error: {exc}",
                metadata=request_metadata,
            ) from exc
        except smtplib.SMTPException as exc:
            raise RetryableEmailProviderError(
                f"SMTP exception: {exc}",
                metadata=request_metadata,
            ) from exc


@lru_cache(maxsize=1)
def build_default_email_provider() -> EmailProvider:
    """Build default email provider from application settings."""
    return SMTPEmailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_tls,
        use_ssl=settings.smtp_use_ssl,
        default_from_email=settings.smtp_from_email,
        default_from_name=settings.smtp_from_name,
        default_timeout_seconds=settings.smtp_timeout_seconds,
    )
