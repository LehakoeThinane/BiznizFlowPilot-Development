"""LinkedIn Lead Sync API poll - v2 upgrade path over the CSV import in
app/api/linkedin_leads.py. Stubbed: no-ops until real API credentials are
configured (LinkedIn's Lead Sync API requires a separate, more restrictive
partner-access approval beyond basic developer access, unverified from
here - see app/integrations/linkedin.py)."""

from __future__ import annotations

import logging
from time import perf_counter

from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.linkedin import poll_new_leads
from app.services.linkedin_leads import LinkedInLeadImportService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="ops.poll_linkedin_leads")
def poll_linkedin_leads_task() -> dict[str, int | str]:
    if not settings.linkedin_client_id:
        logger.info("ops.poll_linkedin_leads.skipped_not_configured")
        return {"status": "skipped_not_configured"}

    started_at = perf_counter()

    with SessionLocal() as db:
        try:
            payloads = poll_new_leads()
            service = LinkedInLeadImportService(db)
            imported = 0
            for payload in payloads:
                if service.import_api_payload(payload):
                    imported += 1
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception("ops.poll_linkedin_leads failed duration_ms=%d", duration_ms)
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info("ops.poll_linkedin_leads completed imported=%d duration_ms=%d", imported, duration_ms)

    return {"status": "ok", "imported": imported}
