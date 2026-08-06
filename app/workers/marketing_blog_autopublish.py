"""Daily blog autopublish Celery task."""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.database import SessionLocal
from app.services.marketing_blog_autopublish import run_daily_autopublish
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.daily_blog_autopublish")
def daily_blog_autopublish_task() -> dict[str, str]:
    """Periodic task: publish one blog post to MM Nexus's marketing site
    per day (see app.services.marketing_blog_autopublish.run_daily_autopublish)."""
    started_at = perf_counter()

    with SessionLocal() as db:
        try:
            result = run_daily_autopublish(db)
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("ops.daily_blog_autopublish failed duration_ms=%d", duration_ms)
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "ops.daily_blog_autopublish completed outcome=%s duration_ms=%d",
        result.get("outcome"), duration_ms,
    )
    return result
