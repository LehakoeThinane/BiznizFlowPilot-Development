"""Log action handler."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.workflow_engine.action_config import ActionResult, BaseActionConfig, LogActionConfig
from app.workflow_engine.action_handlers import ActionHandler


class LogActionHandler(ActionHandler):
    """Simple log action that returns a success payload."""

    action_type = "log"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        """Execute a log action without external side effects."""
        _ = db  # reserved for parity with other handlers
        config = LogActionConfig.model_validate(action_config.model_dump())

        return ActionResult(
            status="success",
            message=config.message,
            data={
                "action_type": config.action_type,
                "context_keys": sorted(context.keys()),
            },
            failure_type=None,
        )
