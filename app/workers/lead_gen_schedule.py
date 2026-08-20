"""Scheduled lead-gen Celery task - runs every active LeadGenSchedule across
every business (Mon/Wed/Thu, see beat_schedule in celery_app.py)."""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.lead_gen_schedule import LeadGenScheduleGlobalService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.run_lead_gen_schedules")
def run_lead_gen_schedules_task() -> dict[str, int | str]:
    """Periodic task: execute every business's active saved Google Places
    searches. Master-switch gated (settings.lead_gen_schedule_enabled) so
    shipping this code doesn't start spending API calls unannounced."""
    if not settings.lead_gen_schedule_enabled:
        return {"status": "skipped", "reason": "lead_gen_schedule_enabled is False"}

    started_at = perf_counter()

    with SessionLocal() as db:
        try:
            result = LeadGenScheduleGlobalService(db).run_all()
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("ops.run_lead_gen_schedules failed duration_ms=%d", duration_ms)
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "ops.run_lead_gen_schedules completed searches_run=%d leads_created=%d "
        "searches_failed=%d followups_sent=%d duration_ms=%d",
        result["searches_run"],
        result["leads_created"],
        result["searches_failed"],
        result["followups_sent"],
        duration_ms,
    )

    return {"status": "ok", **result}
