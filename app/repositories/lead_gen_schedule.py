"""LeadGenSchedule repository - data access layer."""

from sqlalchemy.orm import Session

from app.models.lead_gen_schedule import LeadGenSchedule
from app.repositories.base import BaseRepository


class LeadGenScheduleRepository(BaseRepository[LeadGenSchedule]):
    """LeadGenSchedule repository with business_id filtering.

    🧨 CRITICAL: Every tenant-scoped method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, LeadGenSchedule)

    def list_all_active(self) -> list[LeadGenSchedule]:
        """Every active schedule across every business.

        🧨 Deliberately cross-tenant - only for the scheduled Celery task that
        runs lead-gen for all businesses at once, mirroring
        FollowUpGlobalService.process_all_businesses. Never expose this
        through a tenant-facing API route.
        """
        return self.db.query(LeadGenSchedule).filter(LeadGenSchedule.active.is_(True)).all()
