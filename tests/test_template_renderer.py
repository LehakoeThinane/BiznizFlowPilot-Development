"""Tests for template renderer utility functions."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.workflow_engine.context import MissingTemplateValueError
from app.workflow_engine.template_renderer import (
    render_template_string,
    render_template_value,
)


class TestRenderTemplateString:
    """Tests for render_template_string function."""

    def test_render_template_string_with_simple_values(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a simple template string with context values."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        template = "Lead name: {lead.name}"

        result = render_template_string(test_db, context, template)

        assert result == f"Lead name: {sample_customer.name}"

    def test_render_template_string_with_multiple_placeholders(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering template with multiple placeholder values."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        template = "{lead.name} - {customer.email}"

        result = render_template_string(test_db, context, template)

        assert result == f"{sample_customer.name} - {sample_customer.email}"

    def test_render_template_string_with_no_placeholders(self, test_db: Session, owner_user):
        """Test rendering a template with no placeholders."""
        context = {"business_id": owner_user.business_id}
        template = "Static text with no placeholders"

        result = render_template_string(test_db, context, template)

        assert result == "Static text with no placeholders"

    def test_render_template_string_raises_on_missing_value(
        self, test_db: Session, owner_user
    ):
        """Test that missing template values raise MissingTemplateValueError."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": "non-existent-id",
        }
        template = "{lead.name} is required"

        with pytest.raises(MissingTemplateValueError):
            render_template_string(test_db, context, template)


class TestRenderTemplateValue:
    """Tests for render_template_value function."""

    def test_render_template_value_with_string(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a string value."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = "Contact {lead.name}"

        result = render_template_value(test_db, context, value)

        assert result == f"Contact {sample_customer.name}"

    def test_render_template_value_with_list_of_strings(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a list containing string templates."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = ["Hello {lead.name}", "Email: {customer.email}"]

        result = render_template_value(test_db, context, value)

        assert result == [
            f"Hello {sample_customer.name}",
            f"Email: {sample_customer.email}",
        ]

    def test_render_template_value_with_dict_values(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a dict with string template values."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = {"name": "Contact {lead.name}", "email": "{customer.email}"}

        result = render_template_value(test_db, context, value)

        assert result == {
            "name": f"Contact {sample_customer.name}",
            "email": sample_customer.email,
        }

    def test_render_template_value_with_nested_structure(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering deeply nested structures."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = {
            "level1": {
                "level2": [
                    "Name: {lead.name}",
                    {"level3": "Email: {customer.email}"},
                ]
            }
        }

        result = render_template_value(test_db, context, value)

        assert result == {
            "level1": {
                "level2": [
                    f"Name: {sample_customer.name}",
                    {"level3": f"Email: {sample_customer.email}"},
                ]
            }
        }

    def test_render_template_value_with_non_string_values(
        self, test_db: Session, owner_user
    ):
        """Test that non-string values are returned unchanged."""
        context = {"business_id": owner_user.business_id}
        
        # Integer
        assert render_template_value(test_db, context, 42) == 42
        # Boolean
        assert render_template_value(test_db, context, True) is True
        # None
        assert render_template_value(test_db, context, None) is None
        # Float
        assert render_template_value(test_db, context, 3.14) == 3.14

    def test_render_template_value_with_mixed_list(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a list with mixed types."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = ["Template: {lead.name}", 42, None, True]

        result = render_template_value(test_db, context, value)

        assert result == [f"Template: {sample_customer.name}", 42, None, True]

    def test_render_template_value_with_empty_list(self, test_db: Session, owner_user):
        """Test rendering an empty list."""
        context = {"business_id": owner_user.business_id}
        value = []

        result = render_template_value(test_db, context, value)

        assert result == []

    def test_render_template_value_with_empty_dict(self, test_db: Session, owner_user):
        """Test rendering an empty dict."""
        context = {"business_id": owner_user.business_id}
        value = {}

        result = render_template_value(test_db, context, value)

        assert result == {}

    def test_render_template_value_exceeds_max_depth(
        self, test_db: Session, owner_user
    ):
        """Test that exceeding max_depth raises ValueError."""
        context = {"business_id": owner_user.business_id}
        
        # Create a deeply nested structure
        value = {"a": 1}
        current = value
        for _ in range(15):
            current["nested"] = {}
            current = current["nested"]

        with pytest.raises(ValueError, match="Template payload nesting exceeds max_depth"):
            render_template_value(test_db, context, value, max_depth=10)

    def test_render_template_value_with_custom_max_depth(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering with custom max_depth setting."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        
        # Create a moderately nested structure
        value = {"level1": {"level2": {"level3": "Name: {lead.name}"}}}

        result = render_template_value(test_db, context, value, max_depth=5)

        assert result == {
            "level1": {
                "level2": {"level3": f"Name: {sample_customer.name}"}
            }
        }

    def test_render_template_value_preserves_key_types_in_dict(
        self, test_db: Session, owner_user
    ):
        """Test that dict keys are converted to strings."""
        context = {"business_id": owner_user.business_id}
        value = {1: "numeric_key", "string_key": "value"}

        result = render_template_value(test_db, context, value)

        # Keys should be converted to strings
        assert "1" in result
        assert result["1"] == "numeric_key"
        assert result["string_key"] == "value"

    def test_render_template_value_with_list_of_dicts(
        self, test_db: Session, owner_user, sample_lead, sample_customer
    ):
        """Test rendering a list of dicts with templates."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": str(sample_lead.id),
        }
        value = [
            {"name": "{lead.name}", "type": "lead"},
            {"email": "{customer.email}", "type": "customer"},
        ]

        result = render_template_value(test_db, context, value)

        assert result == [
            {"name": f"{sample_customer.name}", "type": "lead"},
            {"email": sample_customer.email, "type": "customer"},
        ]

    def test_render_template_value_raises_on_missing_template_value(
        self, test_db: Session, owner_user
    ):
        """Test that missing values in nested structures raise error."""
        context = {
            "business_id": owner_user.business_id,
            "entity_type": "lead",
            "entity_id": "non-existent-id",
        }
        value = {"nested": "Name: {lead.name}"}

        with pytest.raises(MissingTemplateValueError):
            render_template_value(test_db, context, value)
