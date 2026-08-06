"""Schemas for the per-user email account/inbox endpoints."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


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
    is_starred: bool = False


class EmailAttachmentInfo(BaseModel):
    filename: str
    size: int
    content_type: str


class EmailMessageDetail(BaseModel):
    uid: str
    from_address: str
    to_address: str
    subject: str
    date: str | None
    body_html: str | None
    body_text: str | None
    attachment_count: int = 0
    attachments: list[EmailAttachmentInfo] = Field(default_factory=list)


class EmailListResponse(BaseModel):
    items: list[EmailMessageSummary]


class EmailFolderResponse(BaseModel):
    name: str
    role: str | None


class EmailFolderListResponse(BaseModel):
    items: list[EmailFolderResponse]


class EmailMessageFlagsUpdate(BaseModel):
    is_starred: bool | None = None
    is_read: bool | None = None

    @model_validator(mode="after")
    def _require_at_least_one_flag(self) -> "EmailMessageFlagsUpdate":
        if self.is_starred is None and self.is_read is None:
            raise ValueError("At least one of is_starred or is_read must be provided.")
        return self


class EmailDisplayPrefsResponse(BaseModel):
    theme: str
    background: str | None


class EmailDisplayPrefsUpdate(BaseModel):
    """Full-replace, not a partial patch - both fields are required so
    background: null is unambiguous ("no background"), not confusable with
    "leave unchanged"."""

    theme: Literal["light", "dark"]
    background: str | None
