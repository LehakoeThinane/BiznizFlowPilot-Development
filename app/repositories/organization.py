"""Organization repository - data access for the Organization model.

NOTE: Organization is a root entity with no business_id, so this does
NOT extend BaseRepository (whose entire contract is business_id
filtering). Cross-tenant tables get their own hand-written repositories.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.organization_domain import OrganizationDomain


class OrganizationRepository:
    """Organization repository (cross-tenant root entity)."""

    def __init__(self, db: Session):
        """Initialize with a DB session."""
        self.db = db

    def get_by_id(self, organization_id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def get_by_domain(self, domain: str) -> Optional[Organization]:
        """Get organization owning the given authorized email domain (case-insensitive)."""
        row = (
            self.db.query(OrganizationDomain)
            .filter(OrganizationDomain.domain == domain.lower())
            .first()
        )
        return row.organization if row else None

    def domain_is_authorized(self, organization_id: UUID, email: str) -> bool:
        """Whether an email's domain matches one of this organization's authorized domains.

        If the organization has no domains configured at all, there is no
        restriction (returns True) - domain restriction is opt-in.
        """
        has_any_domain = (
            self.db.query(OrganizationDomain.id)
            .filter(OrganizationDomain.organization_id == organization_id)
            .first()
            is not None
        )
        if not has_any_domain:
            return True

        email_domain = email.rsplit("@", 1)[-1].lower()
        return (
            self.db.query(OrganizationDomain.id)
            .filter(
                OrganizationDomain.organization_id == organization_id,
                OrganizationDomain.domain == email_domain,
            )
            .first()
            is not None
        )

    def add_domain(
        self, organization_id: UUID, domain: str, is_primary: bool = False
    ) -> OrganizationDomain:
        """Add an authorized domain to an organization."""
        row = OrganizationDomain(
            organization_id=organization_id,
            domain=domain.lower(),
            is_primary=is_primary,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def list_domains(self, organization_id: UUID) -> list[OrganizationDomain]:
        """List an organization's authorized domains."""
        return (
            self.db.query(OrganizationDomain)
            .filter(OrganizationDomain.organization_id == organization_id)
            .order_by(OrganizationDomain.is_primary.desc(), OrganizationDomain.created_at)
            .all()
        )

    def list_all(self, skip: int = 0, limit: int = 50) -> list[Organization]:
        """List organizations (platform admin use)."""
        return (
            self.db.query(Organization)
            .order_by(Organization.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        """Count all organizations."""
        return self.db.query(Organization).count()
