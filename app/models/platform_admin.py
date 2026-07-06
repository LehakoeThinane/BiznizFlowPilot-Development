"""PlatformAdmin model - vendor staff identity, fully separate from tenant `users`.

Never joined with `users` and never shares the `users.role` column - this is
the deliberate fix for the dead `app/api/admin.py` "superadmin" scaffold,
which gated on an unconstrained users.role string that could never
legitimately be set to "superadmin".
"""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String

from app.models.base import BaseModel


class PlatformAdmin(BaseModel):
    """Vendor-side staff account - cross-tenant, own auth boundary."""

    __tablename__ = "platform_admins"
    __table_args__ = (
        CheckConstraint(
            "platform_role IN ('support', 'billing_ops', 'admin', 'super_admin')",
            name="ck_platform_admins_platform_role_valid",
        ),
    )

    email = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Platform admin email (unique)",
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

    platform_role = Column(
        String(20),
        nullable=False,
        server_default="support",
        doc="support | billing_ops | admin | super_admin. Enforced at the "
            "database level - see ck_platform_admins_platform_role_valid.",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this platform admin account is active",
    )

    impersonation_allowed = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Explicit second gate on top of role - granting impersonation is always a deliberate, per-person decision",
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
        return f"<PlatformAdmin id={self.id} email='{self.email}' role='{self.platform_role}'>"
