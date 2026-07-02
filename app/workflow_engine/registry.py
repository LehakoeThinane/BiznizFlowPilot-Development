"""Action handler registry wiring."""

from __future__ import annotations

from app.workflow_engine.action_handlers import ActionHandlerRegistry
from app.workflow_engine.handlers import (
    CreateTaskHandler,
    LogActionHandler,
    SendEmailHandler,
    WebhookHandler,
)


def build_default_action_registry() -> ActionHandlerRegistry:
    """Create registry with built-in handlers for Phase 6."""
    registry = ActionHandlerRegistry()
    registry.register(LogActionHandler())
    registry.register(CreateTaskHandler())
    registry.register(WebhookHandler())
    registry.register(SendEmailHandler())
    return registry
