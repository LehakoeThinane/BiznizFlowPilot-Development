"""Organization model - the umbrella client account above Business (subsidiary)."""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Organization(BaseModel):
    """Organization entity - owns billing, plan tier, and authorized email domains.

    A root entity (no business_id): one Organization can have multiple
    subsidiary Business rows, each with fully isolated CRM/ERP data.

    Authorized email domains live in the separate `organization_domains`
    table (an org may legitimately own more than one domain) - see
    OrganizationDomain.
    """

    __tablename__ = "organizations"

    name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Organization/client name",
    )

    billing_email = Column(
        String(255),
        nullable=False,
        doc="Billing/contact email for the organization",
    )

    plan_tier = Column(
        String(50),
        nullable=False,
        server_default="legacy",
        doc="Subscription plan tier: trial | starter | growth | professional | enterprise | legacy",
    )

    billing_mode = Column(
        String(20),
        nullable=False,
        server_default="organization",
        doc="Where billing is metered: 'organization' (default, one bill for all subsidiaries) | 'subsidiary' (forward-compat, unused by billing logic yet)",
    )

    subscription_status = Column(
        String(20),
        nullable=False,
        server_default="active",
        doc="trial | active | past_due | suspended | cancelled",
    )

    trial_ends_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Trial expiry, if subscription_status is 'trial'",
    )

    trial_reminder_sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Idempotency marker for the trial-expiry reminder email - NULL means not yet sent",
    )

    seats_included = Column(
        Integer,
        nullable=True,
        doc="Plan seat allowance for org-level rollup metering (schema placeholder, no enforcement logic yet)",
    )

    payfast_token = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        doc="PayFast recurring-billing token from the checkout that "
            "provisioned this organization (self-serve signups only - null "
            "for platform-admin-provisioned orgs). The uniqueness "
            "constraint is what makes the ITN handler idempotent: a "
            "redelivered notification can't provision the same customer "
            "twice.",
    )

    # Per-org custom SMTP sender, configured by a platform admin at
    # onboarding (see app/api/platform_admin.py's email-config routes).
    # NULL means not configured - app/services/email.py falls back to the
    # platform-wide Resend/SMTP settings in app/core/config.py.
    smtp_host = Column(String(255), nullable=True, doc="Org's own SMTP relay host, e.g. smtp.office365.com")
    smtp_port = Column(Integer, nullable=True, doc="465 => implicit SSL, anything else => STARTTLS")
    smtp_username = Column(String(255), nullable=True)
    smtp_password_encrypted = Column(
        String(500),
        nullable=True,
        doc="Fernet ciphertext (app/core/crypto.py) - never the plaintext password.",
    )
    smtp_from_email = Column(String(255), nullable=True)
    smtp_from_name = Column(String(255), nullable=True)

    domains = relationship(
        "OrganizationDomain",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Organization id={self.id} name='{self.name}'>"
