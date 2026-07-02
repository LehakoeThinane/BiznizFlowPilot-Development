"""Tests for CreateTaskHandler workflow action handler."""

import pytest
from uuid import uuid4

from app.workflow_engine.action_config import CreateTaskActionConfig
from app.workflow_engine.handlers.create_task import CreateTaskHandler


def _config(title="Follow up with {lead.id}", description=None, assigned_to=None):
    return CreateTaskActionConfig(
        action_type="create_task",
        title=title,
        description=description,
        assigned_to=assigned_to,
    )


@pytest.fixture
def handler():
    return CreateTaskHandler()


@pytest.fixture
def base_context(owner_business):
    return {
        "business_id": str(owner_business.id),
        "entity_type": "lead",
        "entity_id": str(uuid4()),
        "lead": {"id": "LEAD-001"},
    }


# ── success paths ─────────────────────────────────────────────────────────────

class TestCreateTaskHandlerSuccess:
    def test_creates_task_with_minimal_config(self, handler, test_db, base_context):
        cfg = _config(title="Simple task")
        result = handler.execute(db=test_db, action_config=cfg, context=base_context)
        assert result.status == "success"
        assert "task_id" in result.data

    def test_creates_task_with_description(self, handler, test_db, base_context):
        cfg = _config(title="Task", description="A plain description with no templates")
        result = handler.execute(db=test_db, action_config=cfg, context=base_context)
        assert result.status == "success"

    def test_creates_task_with_valid_assigned_to(self, handler, test_db, base_context):
        user_id = str(uuid4())
        cfg = _config(title="Task", assigned_to=user_id)
        result = handler.execute(db=test_db, action_config=cfg, context=base_context)
        assert result.status == "success"

    def test_entity_type_not_lead_no_lead_linkage(self, handler, test_db, owner_business):
        ctx = {
            "business_id": str(owner_business.id),
            "entity_type": "invoice",
            "entity_id": str(uuid4()),
        }
        cfg = _config(title="Invoice task")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        assert result.status == "success"

    def test_no_entity_type_in_context(self, handler, test_db, owner_business):
        ctx = {"business_id": str(owner_business.id)}
        cfg = _config(title="No entity task")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        assert result.status == "success"


# ── failure: invalid assigned_to UUID ─────────────────────────────────────────

class TestCreateTaskHandlerAssignedToFailure:
    def test_invalid_assigned_to_uuid_returns_terminal_failure(self, handler, test_db, base_context):
        cfg = _config(title="Task", assigned_to="not-a-uuid")
        result = handler.execute(db=test_db, action_config=cfg, context=base_context)
        assert result.status == "failure"
        assert "Invalid assigned_to UUID" in result.message

    def test_blank_assigned_to_is_ignored(self, handler, test_db, base_context):
        cfg = _config(title="Task", assigned_to="   ")
        result = handler.execute(db=test_db, action_config=cfg, context=base_context)
        assert result.status == "success"


# ── failure: missing or invalid business_id ───────────────────────────────────

class TestCreateTaskHandlerBusinessIdFailure:
    def test_missing_business_id_returns_failure(self, handler, test_db):
        ctx = {"entity_type": "lead", "entity_id": str(uuid4())}
        cfg = _config(title="Task")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        assert result.status == "failure"
        assert "business_id" in result.message

    def test_invalid_business_id_returns_failure(self, handler, test_db):
        ctx = {"business_id": "not-a-uuid"}
        cfg = _config(title="Task")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        assert result.status == "failure"
        assert "Invalid business_id" in result.message


# ── failure: missing template value ──────────────────────────────────────────

class TestCreateTaskHandlerTemplateMissing:
    def test_missing_template_variable_returns_terminal_failure(self, handler, test_db, owner_business):
        ctx = {"business_id": str(owner_business.id)}
        # Title references {lead.name} but lead key is absent from context
        cfg = _config(title="Follow up with {lead.name}")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        assert result.status == "failure"

    def test_invalid_entity_id_logged_but_not_fatal(self, handler, test_db, owner_business):
        ctx = {
            "business_id": str(owner_business.id),
            "entity_type": "lead",
            "entity_id": "not-a-uuid",
        }
        cfg = _config(title="Task")
        result = handler.execute(db=test_db, action_config=cfg, context=ctx)
        # Invalid UUID for entity_id should log warning but still create the task
        assert result.status == "success"
