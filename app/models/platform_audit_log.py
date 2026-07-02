"""PlatformAuditLog model - append-only trail of vendor-side actions."""

from sqlalchemy import Column, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class PlatformAuditLog(BaseModel):
    """Append-only record of a platform admin action, including failed/denied attempts."""

    __tablename__ = "platform_audit_log"

    platform_admin_id = Column(
        Uuid,
        ForeignKey("platform_admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Acting platform admin (nullable so log entries survive admin deletion)",
    )

    action = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Short action identifier, e.g. 'organization.provision', 'auth.login'",
    )

    target_type = Column(
        String(50),
        nullable=True,
        doc="Type of the acted-upon entity, e.g. 'organization', 'business', 'user'",
    )

    target_id = Column(
        Uuid,
        nullable=True,
        doc="ID of the acted-upon entity",
    )

    result = Column(
        String(20),
        nullable=False,
        server_default="success",
        doc="success | failed | denied",
    )

    meta_data = Column(
        "meta_data",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        doc="Free-form structured detail about the action",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<PlatformAuditLog id={self.id} action='{self.action}' result='{self.result}'>"
