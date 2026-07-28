"""Test for the (currently stubbed) LinkedIn Lead Sync API poll task."""

from __future__ import annotations

from app.core.config import settings
from app.workers.linkedin_lead_poll import poll_linkedin_leads_task


class TestPollLinkedInLeadsTask:
    def test_skips_when_not_configured(self, test_db):
        assert settings.linkedin_client_id == ""
        result = poll_linkedin_leads_task()
        assert result == {"status": "skipped_not_configured"}
