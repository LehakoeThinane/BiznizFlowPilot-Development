"""MarketingCmsAdmin model - identity for MM Nexus's own marketing blog CMS,
fully separate from both tenant `users` and `platform_admins`.

A leaked blog-CMS credential (e.g. a marketing contractor's laptop) must
never be usable against tenant data or platform-admin powers - hence its
own table and its own JWT signing key, never joined with either.
"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.models.base import BaseModel


class MarketingCmsAdmin(BaseModel):
    """Marketing blog CMS staff account - own auth boundary."""

    __tablename__ = "marketing_cms_admins"

    email = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Marketing CMS admin email (unique)",
    )

    hashed_password = Column(
        String(255),
        nullable=False,
        doc="Bcrypt hashed password",
    )

    full_name = Column(
        String(200),
        nullable=False,
        doc="Display name",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this admin account is active",
    )

    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Consecutive failed login attempts since last success",
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Account locked until this UTC time after too many failed logins",
    )

    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of last successful login",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MarketingCmsAdmin id={self.id} email='{self.email}'>"
