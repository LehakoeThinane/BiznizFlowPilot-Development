"""LeadGenSchedule tests - saved-search CRUD, RBAC, and the cross-tenant
scheduled runner (app/workers/lead_gen_schedule.py) that Celery Beat fires
Mon/Wed/Thu."""

from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.integrations.google_places import PlaceResult
from app.models.lead_gen_schedule import LeadGenSchedule
from app.schemas.auth import CurrentUser
from app.schemas.lead_gen_schedule import LeadGenScheduleCreate, LeadGenScheduleUpdate
from app.services.lead_gen_schedule import LeadGenScheduleGlobalService, LeadGenScheduleService
from app.workers.lead_gen_schedule import run_lead_gen_schedules_task


def _fake_places(n: int = 1) -> list[PlaceResult]:
    return [
        PlaceResult(place_id=f"place_{i}", name=f"Biz {i}", address=f"{i} Main St", phone="0110000000", website=None)
        for i in range(n)
    ]


class TestLeadGenScheduleCrud:
    def test_owner_creates_a_schedule(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenScheduleService(test_db)

        schedule = service.create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="hardware stores in Johannesburg")
        )

        assert schedule.query == "hardware stores in Johannesburg"
        assert schedule.max_results == 15
        assert schedule.active is True

    def test_staff_cannot_create_a_schedule(self, test_db: Session, staff_user: CurrentUser):
        service = LeadGenScheduleService(test_db)

        with pytest.raises(PermissionError):
            service.create(staff_user.business_id, staff_user, LeadGenScheduleCreate(query="plumbers"))

    def test_list_only_returns_own_business_schedules(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser
    ):
        service = LeadGenScheduleService(test_db)
        service.create(owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers"))
        service.create(other_user.business_id, other_user, LeadGenScheduleCreate(query="electricians"))

        owner_schedules = service.list(owner_user.business_id, owner_user)

        assert len(owner_schedules) == 1
        assert owner_schedules[0].query == "plumbers"

    def test_update_can_pause_a_schedule(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenScheduleService(test_db)
        schedule = service.create(owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers"))

        updated = service.update(
            owner_user.business_id, owner_user, schedule.id, LeadGenScheduleUpdate(active=False)
        )

        assert updated.active is False
        assert updated.query == "plumbers"  # untouched fields survive partial update

    def test_delete_removes_the_schedule(self, test_db: Session, owner_user: CurrentUser):
        service = LeadGenScheduleService(test_db)
        schedule = service.create(owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers"))

        assert service.delete(owner_user.business_id, owner_user, schedule.id) is True
        assert service.list(owner_user.business_id, owner_user) == []


class TestLeadGenScheduleGlobalRunner:
    def test_runs_active_schedules_across_every_business(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser
    ):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="hardware stores")
        )
        LeadGenScheduleService(test_db).create(
            other_user.business_id, other_user, LeadGenScheduleCreate(query="electricians")
        )

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)):
            result = LeadGenScheduleGlobalService(test_db).run_all()

        assert result["searches_run"] == 2
        assert result["leads_created"] == 2
        assert result["searches_failed"] == 0

    def test_inactive_schedule_is_skipped(self, test_db: Session, owner_user: CurrentUser):
        schedule = LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers")
        )
        LeadGenScheduleService(test_db).update(
            owner_user.business_id, owner_user, schedule.id, LeadGenScheduleUpdate(active=False)
        )

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)) as mock_search:
            result = LeadGenScheduleGlobalService(test_db).run_all()

        mock_search.assert_not_called()
        assert result["searches_run"] == 0

    def test_business_with_no_owner_is_skipped_not_fatal(self, test_db: Session, owner_business):
        """A schedule surviving its owner leaving shouldn't crash the whole run."""
        schedule = LeadGenSchedule(business_id=owner_business.id, query="plumbers", max_results=15, active=True)
        test_db.add(schedule)
        test_db.commit()

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)) as mock_search:
            result = LeadGenScheduleGlobalService(test_db).run_all()

        mock_search.assert_not_called()
        assert result["searches_failed"] == 1
        assert result["searches_run"] == 0

    def test_one_failing_search_does_not_block_the_rest(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser
    ):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="bad query")
        )
        LeadGenScheduleService(test_db).create(
            other_user.business_id, other_user, LeadGenScheduleCreate(query="good query")
        )

        def _raise_for_bad_query(api_key, query, max_results):
            if query == "bad query":
                raise RuntimeError("Places API error")
            return _fake_places(1)

        with patch("app.services.lead_gen.search_text", side_effect=_raise_for_bad_query):
            result = LeadGenScheduleGlobalService(test_db).run_all()

        assert result["searches_failed"] == 1
        assert result["searches_run"] == 1
        assert result["leads_created"] == 1


class TestLeadGenScheduleFollowupWiring:
    """run_all() drafts+sends a follow-up for each newly created lead - only
    an integration/wiring check here, the drafting/sending logic itself is
    covered in tests/test_lead_followup.py."""

    def test_followups_sent_for_leads_with_email_when_ai_configured(
        self, test_db: Session, owner_user: CurrentUser
    ):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers")
        )
        places = [
            PlaceResult(place_id="p1", name="Has Email Co", address="1 Main St", phone="011",
                        website="https://has-email-co.co.za"),
        ]

        with patch("app.services.lead_gen.search_text", return_value=places), \
             patch("app.services.lead_gen.find_email", return_value="prospect@example.com"), \
             patch("app.services.lead_followup.settings.ai_provider", "groq"), \
             patch("app.services.lead_followup.draft_followup_email") as mock_draft, \
             patch("app.services.lead_followup.send_lead_followup_email") as mock_send:
            from app.services.lead_followup import LeadFollowupDraft
            mock_draft.return_value = LeadFollowupDraft(subject="Subj", plain_body="Body")

            result = LeadGenScheduleGlobalService(test_db).run_all()

        assert result["followups_sent"] == 1
        mock_send.assert_called_once()

    def test_no_followups_when_ai_not_configured(self, test_db: Session, owner_user: CurrentUser):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers")
        )

        with patch("app.services.lead_gen.search_text", return_value=_fake_places(1)), \
             patch("app.services.lead_gen.find_email", return_value="prospect@example.com"), \
             patch("app.services.lead_followup.settings.ai_provider", "echo"):
            result = LeadGenScheduleGlobalService(test_db).run_all()

        assert result["followups_sent"] == 0


class TestScheduledLeadGenTaskMasterSwitch:
    """The Celery task itself is gated on settings.lead_gen_schedule_enabled -
    shipping this code must not start spending API calls until someone
    deliberately flips the switch."""

    def test_task_skips_entirely_when_disabled(self, test_db: Session, owner_user: CurrentUser):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers")
        )

        with patch("app.workers.lead_gen_schedule.settings.lead_gen_schedule_enabled", False), \
             patch("app.workers.lead_gen_schedule.SessionLocal", return_value=test_db), \
             patch("app.services.lead_gen.search_text") as mock_search:
            result = run_lead_gen_schedules_task()

        mock_search.assert_not_called()
        assert result["status"] == "skipped"

    def test_task_runs_when_enabled(self, test_db: Session, owner_user: CurrentUser):
        LeadGenScheduleService(test_db).create(
            owner_user.business_id, owner_user, LeadGenScheduleCreate(query="plumbers")
        )

        with patch("app.workers.lead_gen_schedule.settings.lead_gen_schedule_enabled", True), \
             patch("app.workers.lead_gen_schedule.SessionLocal", return_value=test_db), \
             patch("app.services.lead_gen.search_text", return_value=_fake_places(1)):
            result = run_lead_gen_schedules_task()

        assert result["status"] == "ok"
        assert result["searches_run"] == 1


class TestLeadGenScheduleApi:
    def test_create_list_update_delete_via_api(self, client, test_db: Session, registered_user):
        headers = {"Authorization": f"Bearer {registered_user['access_token']}"}

        create_resp = client.post(
            "/api/v1/leads/schedules", json={"query": "law firms in Johannesburg"}, headers=headers
        )
        assert create_resp.status_code == 201, create_resp.text
        schedule_id = create_resp.json()["id"]

        list_resp = client.get("/api/v1/leads/schedules", headers=headers)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1

        patch_resp = client.patch(
            f"/api/v1/leads/schedules/{schedule_id}", json={"active": False}, headers=headers
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["active"] is False

        delete_resp = client.delete(f"/api/v1/leads/schedules/{schedule_id}", headers=headers)
        assert delete_resp.status_code == 200

        assert client.get("/api/v1/leads/schedules", headers=headers).json()["total"] == 0
