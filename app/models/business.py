"""Business model - represents a tenant (subsidiary of an Organization)."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Business(BaseModel):
    """Business/tenant entity - one subsidiary within an Organization.

    NOTE: `email` is a contact address only. It no longer implies a login
    identity — that association only held back when one Business == one
    Organization with a single owner account.
    """

    __tablename__ = "businesses"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_businesses_organization_email"),
    )

    organization_id = Column(
        Uuid,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="Parent Organization (client account) this subsidiary belongs to",
    )

    name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Business name",
    )

    email = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Business contact email (unique per organization, not globally)",
    )

    phone = Column(
        String(20),
        nullable=True,
        doc="Business phone number",
    )

    is_primary_subsidiary = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this was the first subsidiary created for its Organization",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Soft-archive flag; deactivated subsidiaries are hidden but not deleted",
    )

    billed_independently = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Forward-compat: whether this subsidiary is billed separately from its Organization (unused by billing logic yet)",
    )

    seat_limit = Column(
        Integer,
        nullable=True,
        doc="Forward-compat: per-subsidiary seat override (unused by billing logic yet)",
    )

    organization = relationship("Organization", foreign_keys=[organization_id])

    def __repr__(self) -> str:
        """String representation."""
        return f"<Business id={self.id} name='{self.name}'>"
