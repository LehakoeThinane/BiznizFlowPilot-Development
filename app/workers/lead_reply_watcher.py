"""Scheduled lead-reply-watch Celery task - polls every connected mailbox
across every business for a reply from a lead-gen-sourced lead (see
app/services/lead_reply_watcher.py)."""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.lead_reply_watcher import LeadReplyWatcherService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.check_lead_replies")
def check_lead_replies_task() -> dict[str, int | str]:
    """Periodic task: poll every connected mailbox for a reply from a
    lead-gen-sourced lead. Master-switch gated (settings.
    lead_reply_watch_enabled) so shipping this code doesn't start polling
    real mailboxes unannounced."""
    if not settings.lead_reply_watch_enabled:
        return {"status": "skipped", "reason": "lead_reply_watch_enabled is False"}

    started_at = perf_counter()

    with SessionLocal() as db:
        try:
            result = LeadReplyWatcherService(db).check_all_accounts()
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("ops.check_lead_replies failed duration_ms=%d", duration_ms)
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "ops.check_lead_replies completed accounts_checked=%d accounts_failed=%d "
        "leads_escalated=%d duration_ms=%d",
        result["accounts_checked"],
        result["accounts_failed"],
        result["leads_escalated"],
        duration_ms,
    )

    return {"status": "ok", **result}
