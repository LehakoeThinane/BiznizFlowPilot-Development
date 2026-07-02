"""OrganizationDomain model - authorized email domains for an Organization.

Split out from a single organizations.primary_domain column because
real companies (even small ones) often legitimately own more than one
domain (e.g. company.com + company.co.za). Invite-domain validation
checks membership across all of an organization's domains, not just
the primary one.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class OrganizationDomain(BaseModel):
    """An authorized email domain belonging to an Organization."""

    __tablename__ = "organization_domains"
    __table_args__ = (
        UniqueConstraint("domain", name="uq_organization_domains_domain"),
        Index(
            "uq_organization_domains_one_primary",
            "organization_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )

    organization_id = Column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain = Column(
        String(255),
        nullable=False,
        doc="Lowercase domain, no '@' (e.g. 'acmecorp.com')",
    )

    verified = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Vendor-attested at MVP; DNS TXT verification is future work",
    )

    is_primary = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="At most one primary domain per organization (enforced by partial unique index)",
    )

    organization = relationship("Organization", back_populates="domains")

    def __repr__(self) -> str:
        """String representation."""
        return f"<OrganizationDomain id={self.id} domain='{self.domain}'>"
