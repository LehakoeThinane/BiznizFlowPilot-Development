"""MarketingGuideLead repository.

Not a BaseRepository subclass - like PendingCheckout, this model has no
business_id (these are anonymous visitors with no account). Append-only:
every download is its own row, no dedupe/upsert.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.marketing_guide_lead import MarketingGuideLead


class MarketingGuideLeadRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        first_name: str,
        last_name: str,
        email: str,
        company: str,
        guide_slug: str,
        source_page: str | None,
        consented_at: datetime,
    ) -> MarketingGuideLead:
        lead = MarketingGuideLead(
            first_name=first_name,
            last_name=last_name,
            email=email,
            company=company,
            guide_slug=guide_slug,
            source_page=source_page,
            consented_at=consented_at,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead
