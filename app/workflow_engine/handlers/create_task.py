"""Create Task action handler."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.models import Task
from app.workflow_engine.action_config import ActionResult, BaseActionConfig, CreateTaskActionConfig
from app.workflow_engine.action_handlers import ActionHandler
from app.workflow_engine.context import MissingTemplateValueError, render_template_with_context

logger = logging.getLogger(__name__)


class CreateTaskHandler(ActionHandler):
    """Action handler that creates a new task in the CRM."""

    action_type = "create_task"

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        """Execute task creation side effect.
        
        Requires a valid template evaluation and an existing business_id.
        """
        config = CreateTaskActionConfig.model_validate(action_config.model_dump())

        # Safely render all templates via strict context resolution
        try:
            rendered_title = render_template_with_context(db, context, config.title)
            
            rendered_description = None
            if config.description:
                rendered_description = render_template_with_context(db, context, config.description)
                
            assigned_to_id = None
            if config.assigned_to:
                # Could be literal UUID or something like {lead.assigned_to}
                assigned_to_raw = render_template_with_context(db, context, config.assigned_to)
                if assigned_to_raw and assigned_to_raw.strip():
                    try:
                        assigned_to_id = UUID(assigned_to_raw.strip())
                    except ValueError:
                        return ActionResult(
                            status="failure",
                            message=f"Invalid assigned_to UUID: {assigned_to_raw}",
                            failure_type=ActionFailureType.TERMINAL,
                        )
                        
        except MissingTemplateValueError as e:
            return ActionResult(
                status="failure",
                failure_type=ActionFailureType.TERMINAL,
                message=str(e),
            )

        # Context constraints
        business_id_raw = context.get("business_id")
        if not business_id_raw:
            return ActionResult(
                status="failure",
                message="Workflow context missing required 'business_id' for task scope",
                failure_type=ActionFailureType.TERMINAL,
            )
            
        try:
            business_id = UUID(str(business_id_raw))
        except ValueError:
            return ActionResult(
                status="failure",
                message=f"Invalid business_id in context: {business_id_raw}",
                failure_type=ActionFailureType.TERMINAL,
            )

        # Determine linkage
        lead_id = None
        entity_type = context.get("entity_type")
        entity_id_raw = context.get("entity_id")
        
        if entity_type == "lead" and entity_id_raw:
            try:
                lead_id = UUID(str(entity_id_raw))
            except ValueError:
                logger.warning(
                    "CreateTaskHandler: invalid entity_id '%s' in context, skipping lead linkage",
                    entity_id_raw,
                )

        try:
            task = Task(
                business_id=business_id,
                title=rendered_title,
                description=rendered_description,
                assigned_to=assigned_to_id,
                lead_id=lead_id,
                status="pending",
                priority="medium",
            )
            db.add(task)
            db.flush()

            return ActionResult(
                status="success",
                message=f"Created task: {rendered_title}",
                data={"task_id": str(task.id)},
            )
        except IntegrityError as e:
            logger.exception("Constraint violation while creating task from workflow action")
            return ActionResult(
                status="failure",
                message=f"Constraint violation creating task: {e}",
                failure_type=ActionFailureType.TERMINAL,
            )
        except OperationalError as e:
            logger.exception("Database operational error while creating task from workflow action")
            return ActionResult(
                status="failure",
                message=f"Database error creating task: {e}",
                failure_type=ActionFailureType.RETRYABLE,
            )
        except Exception as e:
            logger.exception("Unexpected error while creating task from workflow action")
            return ActionResult(
                status="failure",
                message=f"Unexpected error creating task: {e}",
                failure_type=ActionFailureType.TERMINAL,
            )
