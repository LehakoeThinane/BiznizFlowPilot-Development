"""Tests for workflow context resolution and template rendering."""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.workflow_engine.context import (
    MissingTemplateValueError,
    render_template,
    render_template_with_context,
    resolve_field_path,
    resolve_template_values,
)


@contextmanager
def _count_select_queries(db: Session):
    """Count SELECT statements executed inside the context block."""
    engine = db.get_bind()
    counter = {"count": 0}

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        _ = conn, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith("SELECT"):
            counter["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


class TestWorkflowContextResolver:
    """Context resolver behavior for action execution."""

    def test_resolve_field_path_caches_entity_loads(self, test_db: Session, owner_user, sample_lead, sample_customer):
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }

        with _count_select_queries(test_db) as query_counter:
            first_email = resolve_field_path(test_db, context, "lead.email")
            first_name = resolve_field_path(test_db, context, "lead.name")
            second_email = resolve_field_path(test_db, context, "lead.email")
            customer_email = resolve_field_path(test_db, context, "customer.email")

        assert first_email == sample_customer.email
        assert first_name == sample_customer.name
        assert second_email == sample_customer.email
        assert customer_email == sample_customer.email
        # One query for lead and one for customer for the full block.
        assert query_counter["count"] <= 2

    def test_resolve_field_path_returns_none_for_missing_entity_or_field(self, test_db: Session, owner_user, sample_lead):
        missing_entity_context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(uuid4()),
        }
        missing_field_context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }

        assert resolve_field_path(test_db, missing_entity_context, "lead.email") is None
        assert resolve_field_path(test_db, missing_field_context, "lead.nonexistent_field") is None

    def test_resolve_field_path_from_task_context_reaches_related_entities(
        self,
        test_db: Session,
        owner_user,
        sample_task,
        sample_lead,
        sample_customer,
    ):
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "task",
            "entity_id": str(sample_task.id),
        }

        assert resolve_field_path(test_db, context, "task.title") == sample_task.title
        assert resolve_field_path(test_db, context, "lead.status") == sample_lead.status
        assert resolve_field_path(test_db, context, "customer.email") == sample_customer.email

    def test_resolve_field_path_hides_internal_fields(self, test_db: Session, owner_user, sample_task):
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "task",
            "entity_id": str(sample_task.id),
        }

        assert resolve_field_path(test_db, context, "task.id") is None
        assert resolve_field_path(test_db, context, "task.business_id") is None
        assert resolve_field_path(test_db, context, "task.lead_id") is None
        assert resolve_field_path(test_db, context, "task.created_at") is None


class TestWorkflowTemplateRenderer:
    """Template rendering behavior with resolved context values."""

    def test_render_template_with_resolved_context_values(
        self,
        test_db: Session,
        owner_user,
        sample_lead,
        sample_customer,
    ):
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        template = "Follow up with {lead.name} at {customer.email}"

        values = resolve_template_values(test_db, context, template)
        rendered = render_template(template, values)
        rendered_from_context = render_template_with_context(test_db, context, template)

        expected = f"Follow up with {sample_customer.name} at {sample_customer.email}"
        assert values["lead.name"] == sample_customer.name
        assert values["customer.email"] == sample_customer.email
        assert rendered == expected
        assert rendered_from_context == expected

    def test_render_template_raises_on_missing_value_in_strict_mode(self):
        values = {"lead.name": "Acme Corp", "lead.email": None}
        template = "Email {lead.email} for {lead.name}"

        with pytest.raises(MissingTemplateValueError) as exc_info:
            render_template(template, values, strict=True)

        assert exc_info.value.field_path == "lead.email"

    def test_render_template_substitutes_missing_value_in_non_strict_mode(self):
        values = {"lead.name": "Acme Corp", "lead.email": None}
        template = "Email {lead.email} for {lead.name}"

        rendered = render_template(
            template,
            values,
            strict=False,
            missing_value="[missing]",
        )

        assert rendered == "Email [missing] for Acme Corp"
