"""Organization service - creation and cross-subsidiary management."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository


@dataclass
class ProvisionedShell:
    """Result of provisioning a new Organization + first subsidiary, with no owner User yet."""

    organization: Organization
    business: Business


class OrganizationService:
    """Organization business logic."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.org_repo = OrganizationRepository(db)

    def create_organization_shell(
        self,
        org_name: str,
        billing_email: str,
        subsidiary_name: Optional[str] = None,
        primary_domain: Optional[str] = None,
        plan_tier: str = "trial",
    ) -> ProvisionedShell:
        """Create an Organization and its first (primary) subsidiary Business, with no owner User.

        Used by platform-admin provisioning: ownership is transferred via a
        UserInvitation afterward (see app/api/platform_admin.py), so the
        platform admin never sets or knows the client's password. Caller is
        responsible for commit/rollback boundaries of any surrounding
        transaction (this does not commit).
        """
        organization = Organization(
            name=org_name,
            billing_email=billing_email,
            plan_tier=plan_tier,
        )
        self.db.add(organization)
        self.db.flush()  # get organization.id without committing

        if primary_domain:
            self.org_repo.add_domain(organization.id, primary_domain, is_primary=True)

        business = Business(
            organization_id=organization.id,
            name=subsidiary_name or org_name,
            email=billing_email,
            is_primary_subsidiary=True,
        )
        self.db.add(business)
        self.db.flush()  # get business.id without committing

        return ProvisionedShell(organization=organization, business=business)
