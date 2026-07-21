"""Organization service - creation and cross-subsidiary management."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.models.business import Business
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.services.email import send_trial_reminder_email

TRIAL_PERIOD_DAYS = 14
TRIAL_REMINDER_DAYS_BEFORE_EXPIRY = 3


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
            trial_ends_at=(
                datetime.now(timezone.utc) + timedelta(days=TRIAL_PERIOD_DAYS) if plan_tier == "trial" else None
            ),
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

    def send_due_trial_reminders(self) -> int:
        """Email every trial org within TRIAL_REMINDER_DAYS_BEFORE_EXPIRY of
        expiry that hasn't already been reminded. Idempotent via
        trial_reminder_sent_at - safe to call as often as the periodic task
        runs. Caller is responsible for commit/rollback.
        """
        now = datetime.now(timezone.utc)
        reminder_window_end = now + timedelta(days=TRIAL_REMINDER_DAYS_BEFORE_EXPIRY)

        due = self.org_repo.list_due_for_trial_reminder(now, reminder_window_end)

        sent = 0
        for org in due:
            trial_ends_at = org.trial_ends_at
            if trial_ends_at.tzinfo is None:  # SQLite drops tzinfo on round-trip; always written as UTC
                trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
            days_remaining = max(1, (trial_ends_at - now).days + 1)
            try:
                send_trial_reminder_email(
                    to_email=org.billing_email, org_name=org.name, days_remaining=days_remaining
                )
            except Exception:
                continue  # leave trial_reminder_sent_at unset - retried next run
            org.trial_reminder_sent_at = now
            sent += 1

        return sent

    def set_email_config(
        self,
        organization_id: UUID,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str | None,
        smtp_from_email: str,
        smtp_from_name: str,
    ) -> Optional[Organization]:
        """Set/replace an org's custom SMTP sender. smtp_password=None leaves
        the already-stored (encrypted) password untouched - caller commits."""
        org = self.org_repo.get_by_id(organization_id)
        if not org:
            return None
        org.smtp_host = smtp_host
        org.smtp_port = smtp_port
        org.smtp_username = smtp_username
        if smtp_password:
            org.smtp_password_encrypted = encrypt_secret(smtp_password)
        org.smtp_from_email = smtp_from_email
        org.smtp_from_name = smtp_from_name
        return org

    def clear_email_config(self, organization_id: UUID) -> Optional[Organization]:
        """Revert an org to the platform-default sender - caller commits."""
        org = self.org_repo.get_by_id(organization_id)
        if not org:
            return None
        org.smtp_host = None
        org.smtp_port = None
        org.smtp_username = None
        org.smtp_password_encrypted = None
        org.smtp_from_email = None
        org.smtp_from_name = None
        return org
