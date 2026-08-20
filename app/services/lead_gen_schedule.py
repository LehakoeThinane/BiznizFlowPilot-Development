"""LeadGenSchedule service - saved-search CRUD, and the cross-tenant runner
the scheduled Celery task uses to actually execute them."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import PRIVILEGED_ROLES, require_role
from app.models.lead_gen_schedule import LeadGenSchedule
from app.repositories.business import BusinessRepository
from app.repositories.lead_gen_schedule import LeadGenScheduleRepository
from app.repositories.user import UserRepository
from app.schemas.auth import CurrentUser
from app.schemas.lead_gen_schedule import LeadGenScheduleCreate, LeadGenScheduleUpdate
from app.services.lead_followup import send_followup_to_lead
from app.services.lead_gen import LeadGenService

logger = logging.getLogger(__name__)


class LeadGenScheduleService:
    """Tenant-scoped CRUD for saved lead-gen searches.

    🧨 RBAC: Owner/Manager only - same tier as manual lead-gen (find_via_google_places).
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = LeadGenScheduleRepository(db)

    def create(self, business_id: UUID, current_user: CurrentUser, data: LeadGenScheduleCreate) -> LeadGenSchedule:
        require_role(current_user, PRIVILEGED_ROLES, "create lead-gen schedules")
        return self.repo.create(business_id=business_id, **data.model_dump())

    def list(self, business_id: UUID, current_user: CurrentUser) -> list[LeadGenSchedule]:
        require_role(current_user, PRIVILEGED_ROLES, "view lead-gen schedules")
        return self.repo.list(business_id=business_id, limit=200)

    def update(
        self, business_id: UUID, current_user: CurrentUser, schedule_id: UUID, data: LeadGenScheduleUpdate
    ) -> LeadGenSchedule | None:
        require_role(current_user, PRIVILEGED_ROLES, "update lead-gen schedules")
        updates = data.model_dump(exclude_unset=True)
        return self.repo.update(business_id=business_id, entity_id=schedule_id, **updates)

    def delete(self, business_id: UUID, current_user: CurrentUser, schedule_id: UUID) -> bool:
        require_role(current_user, PRIVILEGED_ROLES, "delete lead-gen schedules")
        return self.repo.delete(business_id=business_id, entity_id=schedule_id)


class LeadGenScheduleGlobalService:
    """Cross-tenant runner for Celery Beat - executes every active schedule.

    Mirrors FollowUpGlobalService (app/services/followup.py): iterates every
    business directly rather than going through a single tenant's session,
    since this is the one legitimate cross-tenant caller in the codebase.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = LeadGenScheduleRepository(db)

    def _owner_actor(self, business_id: UUID) -> CurrentUser | None:
        """Resolve the business's owner as the acting user.

        find_via_google_places creates Leads through LeadService.create,
        which is RBAC-gated (owner/manager only) and attributes the creating
        event to a real user_id - there's no "system user" concept in this
        codebase to fall back to, so the actual business owner is the
        correct actor for an automated, on-their-behalf action.
        """
        owners = UserRepository(self.db).list_by_role(business_id, "owner")
        owner = next((u for u in owners if u.is_active), None)
        if owner is None:
            return None
        return CurrentUser(
            user_id=owner.id,
            business_id=business_id,
            email=owner.email,
            role=owner.role,
            full_name=f"{owner.first_name} {owner.last_name}",
        )

    def run_all(self) -> dict[str, int]:
        """Run every active schedule across every business.

        A failure on one schedule (bad query, API error, no owner found)
        is logged and skipped rather than aborting the whole run - the same
        "one bad item doesn't block the rest" shape as process_all_businesses.
        """
        schedules = self.repo.list_all_active()
        service = LeadGenService(self.db)
        business_repo = BusinessRepository(self.db)

        searches_run = 0
        leads_created = 0
        searches_failed = 0
        followups_sent = 0

        for schedule in schedules:
            actor = self._owner_actor(schedule.business_id)
            if actor is None:
                logger.warning(
                    "lead_gen_schedule %s skipped - no active owner user for business %s",
                    schedule.id,
                    schedule.business_id,
                )
                searches_failed += 1
                continue

            try:
                result = service.find_via_google_places(
                    schedule.business_id,
                    actor,
                    query=schedule.query,
                    max_results=schedule.max_results,
                )
                searches_run += 1
                leads_created += len(result.leads)
            except Exception:
                logger.exception(
                    "lead_gen_schedule %s failed (business=%s, query=%r)",
                    schedule.id,
                    schedule.business_id,
                    schedule.query,
                )
                searches_failed += 1
                continue

            if not result.leads:
                continue

            business = business_repo.get_by_id(schedule.business_id)
            business_name = business.name if business else "Us"
            organization_id = business.organization_id if business else None

            for lead in result.leads:
                try:
                    if send_followup_to_lead(self.db, lead, business_name, organization_id):
                        followups_sent += 1
                except Exception:
                    # A failed send doesn't get retried later - the lead was
                    # already created and won't be re-imported on a future
                    # run (external_ref dedup), so this is logged as the
                    # only record of the miss rather than silently lost.
                    logger.exception("lead_followup send failed for lead %s", lead.id)

        return {
            "searches_run": searches_run,
            "leads_created": leads_created,
            "searches_failed": searches_failed,
            "followups_sent": followups_sent,
        }
