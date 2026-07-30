"""LinkedInLead repository.

Not a BaseRepository subclass - like MarketingGuideLead, this model has no
business_id (these are MM Nexus's own sales leads, not tenant data).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.linkedin_lead import LinkedInLead


class LinkedInLeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_linkedin_lead_id(self, linkedin_lead_id: str) -> LinkedInLead | None:
        return self.db.query(LinkedInLead).filter(LinkedInLead.linkedin_lead_id == linkedin_lead_id).first()

    def get_by_id(self, lead_id: UUID) -> LinkedInLead | None:
        return self.db.query(LinkedInLead).filter(LinkedInLead.id == lead_id).first()

    def create(
        self,
        linkedin_lead_id: str,
        first_name: str,
        last_name: str,
        email: str,
        ingestion_source: str,
        company: str | None = None,
        job_title: str | None = None,
        phone: str | None = None,
        campaign_name: str | None = None,
        form_name: str | None = None,
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        submitted_at: datetime | None = None,
    ) -> LinkedInLead:
        lead = LinkedInLead(
            linkedin_lead_id=linkedin_lead_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            company=company,
            job_title=job_title,
            phone=phone,
            campaign_name=campaign_name,
            form_name=form_name,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            ingestion_source=ingestion_source,
            submitted_at=submitted_at,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    def update_status(
        self, lead_id: UUID, status: str | None = None, assigned_to: str | None = None,
    ) -> LinkedInLead | None:
        lead = self.get_by_id(lead_id)
        if not lead:
            return None
        if status is not None:
            lead.status = status
        if assigned_to is not None:
            lead.assigned_to = assigned_to
        self.db.commit()
        self.db.refresh(lead)
        return lead
