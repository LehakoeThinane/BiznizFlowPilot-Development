"""MarketingCmsAdmin repository - data access for the cross-cutting
marketing_cms_admins table.

Not a BaseRepository subclass - MarketingCmsAdmin has no business_id, and
must never be queried alongside tenant `users` or `platform_admins`.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.marketing_cms_admin import MarketingCmsAdmin


class MarketingCmsAdminRepository:
    """Marketing CMS admin repository."""

    def __init__(self, db: Session):
        """Initialize with a DB session."""
        self.db = db

    def get_by_email(self, email: str) -> Optional[MarketingCmsAdmin]:
        """Look up a marketing CMS admin by email."""
        return self.db.query(MarketingCmsAdmin).filter(MarketingCmsAdmin.email == email).first()

    def get_by_id(self, admin_id) -> Optional[MarketingCmsAdmin]:
        """Look up a marketing CMS admin by ID."""
        return self.db.query(MarketingCmsAdmin).filter(MarketingCmsAdmin.id == admin_id).first()
