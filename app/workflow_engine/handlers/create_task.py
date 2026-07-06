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

        action_id_raw = context.get("action_id")
        source_action_id = UUID(str(action_id_raw)) if action_id_raw else None

        if source_action_id is not None:
            existing = (
                db.query(Task)
                .filter(Task.source_workflow_action_id == source_action_id)
                .first()
            )
            if existing is not None:
                # A prior attempt for this exact action already created the
                # task (this run is a retry after an ambiguous outcome, e.g.
                # the insert committed but the executor never got to record
                # it before a crash). Report the existing task instead of
                # creating a second one.
                return ActionResult(
                    status="success",
                    message=f"Task already created by a previous attempt: {existing.title}",
                    data={"task_id": str(existing.id), "idempotent_replay": True},
                )

        try:
            # Scoped to a SAVEPOINT rather than the outer session: if this
            # insert collides on the idempotency constraint below, only this
            # attempt is undone - not the rest of the run's already-flushed
            # bookkeeping, which shares this same session/transaction.
            with db.begin_nested():
                task = Task(
                    business_id=business_id,
                    title=rendered_title,
                    description=rendered_description,
                    assigned_to=assigned_to_id,
                    lead_id=lead_id,
                    status="pending",
                    priority="medium",
                    source_workflow_action_id=source_action_id,
                )
                db.add(task)
                db.flush()

            return ActionResult(
                status="success",
                message=f"Created task: {rendered_title}",
                data={"task_id": str(task.id)},
            )
        except IntegrityError as e:
            if source_action_id is not None:
                existing = (
                    db.query(Task)
                    .filter(Task.source_workflow_action_id == source_action_id)
                    .first()
                )
                if existing is not None:
                    # Lost the race against another concurrent attempt for
                    # the same action - not a real failure, the task exists.
                    return ActionResult(
                        status="success",
                        message=f"Task already created by a previous attempt: {existing.title}",
                        data={"task_id": str(existing.id), "idempotent_replay": True},
                    )
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
