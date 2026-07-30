"""LinkedInLead model - a top-of-funnel sales lead captured via a LinkedIn
ad, either a native Lead Gen Form (filled out inside LinkedIn's feed) or a
click-through to our own landing page. Root-level, like MarketingGuideLead/
PendingCheckout - unrelated to any Organization/Business, since these are
MM Nexus's own prospects, not tenant CRM data (see app/models/lead.py for
the tenant-scoped CRM Lead, which this is NOT).

Ingested via one of three paths that all write to this same table (see
app/services/linkedin_leads.py): a manual CSV export/upload from Campaign
Manager (ingestion_source="csv_import", works with zero LinkedIn API
approval), our own landing page's form (ingestion_source="landing_page"),
or - once/if LinkedIn grants Lead Sync API partner access - an automated
Celery Beat poll (ingestion_source="api_poll"). Downstream scoring/routing/
notification code never needs to know which path produced a row.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, String

from app.models.base import BaseModel


class LinkedInLead(BaseModel):
    __tablename__ = "linkedin_leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'contacted', 'qualified', 'disqualified')",
            name="ck_linkedin_leads_status",
        ),
        CheckConstraint(
            "ingestion_source IN ('csv_import', 'api_poll', 'landing_page')",
            name="ck_linkedin_leads_ingestion_source",
        ),
    )

    linkedin_lead_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="LinkedIn's own lead identifier - the idempotency key, present in "
            "both the Campaign Manager CSV export and the Lead Sync API payload. "
            "For landing_page rows (which LinkedIn never assigns an ID to), this "
            "is a locally generated UUID string instead.",
    )
    campaign_name = Column(String(255), nullable=True)
    form_name = Column(String(255), nullable=True)

    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=True)
    job_title = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    utm_source = Column(String(255), nullable=True)
    utm_medium = Column(String(255), nullable=True)
    utm_campaign = Column(String(255), nullable=True)

    ingestion_source = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="new", server_default="new")
    assigned_to = Column(
        String(255),
        nullable=True,
        doc="Free-text owner (e.g. staff name/email) - small team, not a real "
            "assignment engine. Upgrade to a platform_admin_id FK later if a "
            "second staff member ever needs real routing.",
    )
    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the visitor submitted the form, per LinkedIn's own timestamp "
            "(csv_import/api_poll) or our own server clock (landing_page).",
    )

    def __repr__(self) -> str:
        return f"<LinkedInLead id={self.id} email='{self.email}' status='{self.status}'>"
