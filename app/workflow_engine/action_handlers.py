"""Workflow action handler interface and registry contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from app.workflow_engine.action_config import ActionResult, BaseActionConfig


class ActionHandler(ABC):
    """Interface for action handlers executed by the workflow engine."""

    action_type: str

    @abstractmethod
    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        """Execute one materialized workflow action and return normalized result.

        Handler implementations should validate/cast `action_config` into their
        concrete schema (for example `WebhookActionConfig`) before use.
        """


class ActionHandlerRegistry:
    """Registry mapping action types to concrete handlers."""

    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        """Register (or replace) a handler by action type."""
        action_type = handler.action_type.strip().lower()
        if not action_type:
            raise ValueError("Handler action_type must be non-empty")
        self._handlers[action_type] = handler

    def get(self, action_type: str) -> ActionHandler:
        """Resolve a handler for the given action type."""
        key = action_type.strip().lower()
        if key not in self._handlers:
            raise KeyError(f"No handler registered for action_type '{action_type}'")
        return self._handlers[key]

    def supports(self, action_type: str) -> bool:
        """Check whether a handler exists for action type."""
        return action_type.strip().lower() in self._handlers

    def registered_action_types(self) -> list[str]:
        """Return sorted list of known action types."""
        return sorted(self._handlers.keys())
