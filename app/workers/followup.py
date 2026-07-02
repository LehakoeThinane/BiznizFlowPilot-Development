"""Automated follow-up Celery tasks.

Implements scheduled checks for:
- Idle lead follow-up task creation
- Overdue task status marking
"""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.database import SessionLocal
from app.services.followup import FollowUpGlobalService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.process_followups")
def process_followups_task(idle_hours: int = 24) -> dict[str, int | str]:
    """Periodic task to process automated follow-ups across all tenants.
    
    This task:
    1. Finds leads idle for more than `idle_hours`
    2. Creates follow-up tasks for idle leads  
    3. Marks overdue tasks past their due dates
    4. Emits events for notification processing
    """
    started_at = perf_counter()
    
    with SessionLocal() as db:
        try:
            service = FollowUpGlobalService(db)
            total_actions = service.process_all_businesses(
                idle_hours=idle_hours,
            )
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception(
                "ops.process_followups failed duration_ms=%d idle_hours=%d",
                duration_ms,
                idle_hours,
            )
            raise
    
    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "ops.process_followups completed total_actions=%d duration_ms=%d idle_hours=%d",
        total_actions,
        duration_ms,
        idle_hours,
    )
    
    return {
        "status": "ok",
        "total_actions": total_actions,
    }
