"""MarketingGuideLead model - a top-of-funnel sales lead captured when an
anonymous marketing-site visitor downloads a gated guide.

Root-level, like PendingCheckout - unrelated to any Organization/Business,
since these visitors have no account yet. No CheckConstraint on guide_slug
(unlike PendingCheckout.status): guide topics are marketing content that
will change without needing a migration, not a fixed state machine.
"""

from sqlalchemy import Column, DateTime, String

from app.models.base import BaseModel


class MarketingGuideLead(BaseModel):
    __tablename__ = "marketing_guide_leads"

    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False)
    guide_slug = Column(String(100), nullable=False)
    source_page = Column(String(255), nullable=True)
    consented_at = Column(DateTime(timezone=True), nullable=False, doc="When the visitor ticked the consent checkbox.")

    def __repr__(self) -> str:
        return f"<MarketingGuideLead id={self.id} email='{self.email}' guide_slug='{self.guide_slug}'>"
