"""Tests for app/ai/tools.py's business-action executors, against a real
test DB and the real TaskService/LeadService/CustomerService."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.ai.tools import execute_add_note, execute_create_task, execute_update_lead_status
from app.models.customer import Customer
from app.schemas.auth import CurrentUser
from app.schemas.lead import LeadCreate
from app.services.lead import LeadService


class TestExecuteCreateTask:
    def test_creates_task_with_explicit_assignee(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser):
        result = execute_create_task(
            test_db, owner_user.business_id, owner_user,
            {"title": "Call Acme", "assigned_to": str(manager_user.user_id)},
        )
        assert result["title"] == "Call Acme"

        from app.models.task import Task
        task = test_db.query(Task).filter(Task.id == UUID(result["task_id"])).first()
        assert task.assigned_to == manager_user.user_id

    def test_assigned_to_me_resolves_to_current_user(self, test_db: Session, owner_user: CurrentUser):
        result = execute_create_task(test_db, owner_user.business_id, owner_user, {"title": "Follow up", "assigned_to": "me"})

        from app.models.task import Task
        task = test_db.query(Task).filter(Task.id == UUID(result["task_id"])).first()
        assert task.assigned_to == owner_user.user_id

    def test_no_assignee_leaves_unassigned(self, test_db: Session, owner_user: CurrentUser):
        result = execute_create_task(test_db, owner_user.business_id, owner_user, {"title": "Unassigned task"})
        from app.models.task import Task
        task = test_db.query(Task).filter(Task.id == UUID(result["task_id"])).first()
        assert task.assigned_to is None


class TestExecuteUpdateLeadStatus:
    def test_valid_transition_succeeds(self, test_db: Session, owner_user: CurrentUser):
        service = LeadService(test_db)
        lead = service.create(owner_user.business_id, owner_user, LeadCreate(status="new", source="web_form"))

        result = execute_update_lead_status(
            test_db, owner_user.business_id, owner_user, {"lead_id": str(lead.id), "new_status": "contacted"}
        )
        assert result["status"] == "contacted"

    def test_invalid_transition_raises_value_error(self, test_db: Session, owner_user: CurrentUser):
        service = LeadService(test_db)
        lead = service.create(owner_user.business_id, owner_user, LeadCreate(status="new", source="web_form"))

        with pytest.raises(ValueError, match="Invalid state transition"):
            execute_update_lead_status(
                test_db, owner_user.business_id, owner_user, {"lead_id": str(lead.id), "new_status": "won"}
            )

    def test_unknown_lead_raises_value_error(self, test_db: Session, owner_user: CurrentUser):
        import uuid

        with pytest.raises(ValueError, match="Lead not found"):
            execute_update_lead_status(
                test_db, owner_user.business_id, owner_user, {"lead_id": str(uuid.uuid4()), "new_status": "contacted"}
            )


class TestExecuteAddNote:
    def test_appends_to_existing_lead_notes(self, test_db: Session, owner_user: CurrentUser):
        service = LeadService(test_db)
        lead = service.create(owner_user.business_id, owner_user, LeadCreate(status="new", source="web_form", notes="Original note"))

        result = execute_add_note(
            test_db, owner_user.business_id, owner_user,
            {"entity_type": "lead", "entity_id": str(lead.id), "note_text": "Called, left voicemail"},
        )
        assert "Original note" in result["notes"]
        assert "Called, left voicemail" in result["notes"]

    def test_client_note_appends(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        result = execute_add_note(
            test_db, owner_user.business_id, owner_user,
            {"entity_type": "client", "entity_id": str(sample_customer.id), "note_text": "Sent proposal"},
        )
        assert "Sent proposal" in result["notes"]

    def test_unsupported_entity_type_raises(self, test_db: Session, owner_user: CurrentUser):
        with pytest.raises(ValueError, match="Unsupported entity_type"):
            execute_add_note(
                test_db, owner_user.business_id, owner_user,
                {"entity_type": "supplier", "entity_id": "00000000-0000-0000-0000-000000000000", "note_text": "x"},
            )
