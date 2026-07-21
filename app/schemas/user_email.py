"""Schemas for the per-user email account/inbox endpoints."""

from pydantic import BaseModel, EmailStr, Field


class UserEmailAccountUpdate(BaseModel):
    """Connect/update the caller's own mailbox.

    imap_password/smtp_password are write-only and optional: omit or pass
    null to leave the already-stored (encrypted) password unchanged - only
    send a value when actually replacing it.
    """

    imap_host: str = Field(..., min_length=1, max_length=255)
    imap_port: int = Field(..., ge=1, le=65535)
    imap_username: str = Field(..., min_length=1, max_length=255)
    imap_password: str | None = Field(default=None, min_length=1)

    smtp_host: str = Field(..., min_length=1, max_length=255)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_username: str = Field(..., min_length=1, max_length=255)
    smtp_password: str | None = Field(default=None, min_length=1)
    smtp_from_email: EmailStr
    smtp_from_name: str = Field(..., min_length=1, max_length=255)


class UserEmailAccountResponse(BaseModel):
    """Never echoes real passwords - only whether one is stored."""

    imap_host: str | None
    imap_port: int | None
    imap_username: str | None
    imap_password_set: bool
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_password_set: bool
    smtp_from_email: str | None
    smtp_from_name: str | None


class EmailMessageSummary(BaseModel):
    uid: str
    from_address: str
    subject: str
    date: str | None
    is_read: bool


class EmailMessageDetail(BaseModel):
    uid: str
    from_address: str
    to_address: str
    subject: str
    date: str | None
    body_html: str | None
    body_text: str | None


class EmailListResponse(BaseModel):
    items: list[EmailMessageSummary]


class EmailSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
