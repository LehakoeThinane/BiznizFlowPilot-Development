"""Deterministic action handlers for load-test scenarios."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import ActionResult, BaseActionConfig
from app.workflow_engine.action_handlers import ActionHandler, ActionHandlerRegistry
from app.workflow_engine.context import MissingTemplateValueError, render_template_with_context


class AlwaysSucceedHandler(ActionHandler):
    """Always returns success for deterministic throughput tests."""

    # Uses existing typed config contract for parser compatibility.
    action_type = "log"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        _ = db, action_config, context
        return ActionResult(
            status="success",
            message="always_succeed",
            data={"handler": "AlwaysSucceedHandler"},
            failure_type=None,
        )


class AlwaysFailTerminalHandler(ActionHandler):
    """Always returns terminal failure without retries."""

    action_type = "create_task"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        _ = db, action_config, context
        return ActionResult(
            status="failure",
            message="terminal failure injected by load test",
            data={"handler": "AlwaysFailTerminalHandler"},
            failure_type=ActionFailureType.TERMINAL,
        )


class AlwaysFailRetryableHandler(ActionHandler):
    """Always returns retryable failure to exercise retry exhaustion."""

    action_type = "webhook"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        _ = db, action_config, context
        return ActionResult(
            status="failure",
            message="retryable failure injected by load test",
            data={"handler": "AlwaysFailRetryableHandler"},
            failure_type=ActionFailureType.RETRYABLE,
        )


class SlowHandler(ActionHandler):
    """Sleeps for a requested duration, then applies timeout semantics."""

    # Uses send_email config so timeout_seconds is available on BaseActionConfig.
    action_type = "send_email"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        _ = db, context
        payload = action_config.model_dump()
        timeout_seconds = payload.get("timeout_seconds")

        raw_sleep = payload.get("body_template", "0")
        try:
            sleep_seconds = float(str(raw_sleep))
        except (TypeError, ValueError):
            sleep_seconds = 0.0

        sleep_for = sleep_seconds
        if timeout_seconds is not None:
            sleep_for = min(sleep_seconds, float(timeout_seconds))
        started_at = time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)
        elapsed = time.monotonic() - started_at

        if timeout_seconds is not None and elapsed >= float(timeout_seconds):
            return ActionResult(
                status="failure",
                message=(
                    f"handler timed out after {elapsed:.2f}s "
                    f"(timeout_seconds={float(timeout_seconds):.2f})"
                ),
                data={"handler": "SlowHandler"},
                failure_type=ActionFailureType.TERMINAL,
            )

        return ActionResult(
            status="success",
            message=f"slow handler completed in {elapsed:.2f}s",
            data={"handler": "SlowHandler"},
            failure_type=None,
        )


class ContextRenderingCreateTaskHandler(ActionHandler):
    """Renders create_task title template via context resolver for isolation checks."""

    action_type = "create_task"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        payload = action_config.model_dump()
        template = str(payload.get("title", ""))
        try:
            rendered_message = render_template_with_context(db, context, template)
        except MissingTemplateValueError as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                data={"handler": "ContextRenderingCreateTaskHandler"},
                failure_type=ActionFailureType.TERMINAL,
            )

        return ActionResult(
            status="success",
            message=rendered_message,
            data={
                "handler": "ContextRenderingCreateTaskHandler",
                "rendered_message": rendered_message,
            },
            failure_type=None,
        )


def build_test_handler_registry() -> ActionHandlerRegistry:
    """Build deterministic registry for load tests."""
    registry = ActionHandlerRegistry()
    registry.register(AlwaysSucceedHandler())
    registry.register(AlwaysFailTerminalHandler())
    registry.register(AlwaysFailRetryableHandler())
    registry.register(SlowHandler())
    return registry


def build_isolation_handler_registry() -> ActionHandlerRegistry:
    """Build handler registry focused on context rendering assertions."""
    registry = ActionHandlerRegistry()
    registry.register(ContextRenderingCreateTaskHandler())
    return registry
