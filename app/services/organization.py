"""Organization service - creation and cross-subsidiary management."""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization import OrganizationRepository


@dataclass
class ProvisionedAccount:
    """Result of provisioning a new Organization + first subsidiary + owner."""

    organization: Organization
    business: Business
    owner: User


class OrganizationService:
    """Organization business logic."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.org_repo = OrganizationRepository(db)

    def create_organization_with_first_subsidiary(
        self,
        org_name: str,
        billing_email: str,
        owner_email: str,
        owner_password: str,
        owner_first_name: str,
        owner_last_name: str,
        subsidiary_name: Optional[str] = None,
        primary_domain: Optional[str] = None,
        plan_tier: str = "trial",
    ) -> ProvisionedAccount:
        """Create an Organization, its first (primary) subsidiary Business, and the owner User.

        Single shared code path used by both self-service registration
        (AuthService.register) and platform-admin provisioning, so there
        is exactly one place that creates this Organization+Business+User
        triple. Caller is responsible for commit/rollback boundaries of
        any surrounding transaction (this does not commit).

        Raises:
            ValueError: If owner_email is already registered.
        """
        existing_user = self.db.query(User).filter(User.email == owner_email).first()
        if existing_user:
            raise ValueError("An account with this email already exists")

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

        owner = User(
            business_id=business.id,
            email=owner_email,
            first_name=owner_first_name,
            last_name=owner_last_name,
            hashed_password=hash_password(owner_password),
            role="owner",
            is_active=True,
        )
        self.db.add(owner)
        self.db.flush()

        return ProvisionedAccount(organization=organization, business=business, owner=owner)
