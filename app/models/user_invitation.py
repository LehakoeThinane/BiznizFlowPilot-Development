"""UserInvitation model - domain-restricted employee onboarding.

Token design mirrors the existing password-reset flow's intent
(single-use, expiring) but not its mechanism: password reset uses a
stateless signed JWT; invites need to be listable/revocable by an admin
before acceptance, so they're DB-backed rows with a hashed token, not a
bare JWT.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserInvitation(BaseModel):
    """A pending (or resolved) invitation for someone to join a Business."""

    __tablename__ = "user_invitations"
    __table_args__ = (
        Index(
            "uq_user_invitations_pending_business_email",
            "business_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization_id = Column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Denormalized from business.organization_id to avoid a join on every domain check",
    )

    email = Column(String(255), nullable=False, index=True)

    role = Column(
        String(50),
        nullable=False,
        server_default="staff",
        doc="Role the invitee will get on acceptance: owner|manager|staff|it_admin",
    )

    invited_by = Column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    token_hash = Column(
        String(128),
        nullable=False,
        unique=True,
        doc="sha256 hex digest of the raw invite token; raw token only ever exists in the email",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
        doc="pending | accepted | revoked | expired",
    )

    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    business = relationship("Business", foreign_keys=[business_id])
    organization = relationship("Organization", foreign_keys=[organization_id])

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserInvitation id={self.id} email='{self.email}' status='{self.status}'>"
