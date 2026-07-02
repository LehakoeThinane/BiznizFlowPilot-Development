"""Tests for Phase 5 artifact contracts (config, retry, handlers)."""

from __future__ import annotations

import pytest

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import (
    ActionResult,
    RetryPolicy,
    parse_action_config,
)
from app.workflow_engine.action_handlers import ActionHandler, ActionHandlerRegistry
from app.workflow_engine.handlers import LogActionHandler
from app.workflow_engine.registry import build_default_action_registry


class TestActionConfigArtifacts:
    """Typed config and result contracts."""

    def test_parse_action_config_discriminated_union(self):
        config = parse_action_config(
            {
                "action_type": "webhook",
                "url": "https://example.com/hook",
                "method": "POST",
                "retry_policy": {
                    "max_attempts": 3,
                },
                "continue_on_failure": False,
            }
        )

        assert config.action_type == "webhook"
        assert config.retry_policy.max_attempts == 3

    def test_retry_policy_branches_by_failure_type(self):
        policy = RetryPolicy(max_attempts=2)

        assert policy.should_retry(ActionFailureType.RETRYABLE, attempt_count=0) is True
        assert policy.should_retry(ActionFailureType.TERMINAL, attempt_count=0) is False
        assert policy.should_retry(ActionFailureType.SKIPPABLE, attempt_count=0) is False
        assert policy.should_retry(ActionFailureType.RETRYABLE, attempt_count=2) is False

    def test_action_result_contract(self):
        result = ActionResult(
            status="failure",
            message="Webhook timed out",
            failure_type=ActionFailureType.RETRYABLE,
            data={"status_code": 504},
        )

        assert result.status == "failure"
        assert result.failure_type == ActionFailureType.RETRYABLE
        assert result.data["status_code"] == 504


class _StubHandler(ActionHandler):
    action_type = "log"

    def execute(self, *, db, action_config, context):  # pragma: no cover - contract stub
        return ActionResult(status="success", message="ok")


class TestActionHandlerRegistryArtifacts:
    """Action handler interface + registry contract."""

    def test_registry_register_and_get(self):
        registry = ActionHandlerRegistry()
        handler = _StubHandler()

        registry.register(handler)

        resolved = registry.get("log")
        assert resolved is handler
        assert registry.supports("log") is True
        assert registry.registered_action_types() == ["log"]

    def test_registry_missing_handler_raises(self):
        registry = ActionHandlerRegistry()

        with pytest.raises(KeyError, match="No handler registered"):
            registry.get("webhook")

    def test_default_registry_includes_log_handler(self):
        registry = build_default_action_registry()

        resolved = registry.get("log")
        assert isinstance(resolved, LogActionHandler)
        assert registry.supports("webhook") is True
        assert registry.supports("send_email") is True

    def test_log_action_handler_returns_success_result(self, test_db):
        handler = LogActionHandler()
        action_config = parse_action_config(
            {
                "action_type": "log",
                "message": "hello world",
            }
        )

        result = handler.execute(db=test_db, action_config=action_config, context={"run_id": "123"})
        assert result.status == "success"
        assert result.message == "hello world"
