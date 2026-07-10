"""Trial-expiry reminder Celery task."""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.database import SessionLocal
from app.services.organization import OrganizationService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.send_trial_reminders")
def send_trial_reminders_task() -> dict[str, int | str]:
    """Periodic task: email every trial org within a few days of expiry that
    hasn't already been reminded (see OrganizationService.send_due_trial_reminders)."""
    started_at = perf_counter()

    with SessionLocal() as db:
        try:
            sent = OrganizationService(db).send_due_trial_reminders()
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("ops.send_trial_reminders failed duration_ms=%d", duration_ms)
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info("ops.send_trial_reminders completed sent=%d duration_ms=%d", sent, duration_ms)

    return {"status": "ok", "sent": sent}
