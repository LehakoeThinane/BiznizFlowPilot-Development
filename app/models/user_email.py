"""UserEmailAccount model - each employee's own connected mailbox
(IMAP for reading, SMTP for sending), separate from the org-wide SMTP
sender on Organization (which is only used for system-generated emails
like meeting invites)."""

from sqlalchemy import Column, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserEmailAccount(BaseModel):
    """A user's self-connected personal mailbox. Strictly 1:1 with User."""

    __tablename__ = "user_email_accounts"

    user_id = Column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True,
        doc="Owning user - strictly 1:1, one mailbox per user",
    )
    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY, defense-in-depth alongside user_id",
    )

    imap_host = Column(String(255), nullable=True)
    imap_port = Column(Integer, nullable=True, doc="993 => implicit SSL, anything else => STARTTLS")
    imap_username = Column(String(255), nullable=True)
    imap_password_encrypted = Column(
        String(500), nullable=True, doc="Fernet ciphertext (app/core/crypto.py) - never the plaintext password.",
    )

    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True, doc="465 => implicit SSL, anything else => STARTTLS")
    smtp_username = Column(String(255), nullable=True)
    smtp_password_encrypted = Column(
        String(500), nullable=True, doc="Fernet ciphertext (app/core/crypto.py) - never the plaintext password.",
    )
    smtp_from_email = Column(String(255), nullable=True)
    smtp_from_name = Column(String(255), nullable=True)

    email_theme = Column(
        String(10), nullable=False, server_default="dark",
        doc="Email-page-scoped display preference, independent of IMAP/SMTP config - 'light' or 'dark'.",
    )
    email_background = Column(
        String(50), nullable=True, doc="Preset background key for the Email page, or NULL for none.",
    )

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<UserEmailAccount id={self.id} user_id={self.user_id}>"
