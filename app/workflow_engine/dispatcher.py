"""Workflow dispatcher for Phase 4 event-to-run materialization."""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Event, WorkflowRun
from app.repositories.workflow import WorkflowActionRepository, WorkflowRunRepository
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.definition_provider import DefinitionProvider
from app.workflow_engine.condition_evaluator import evaluate_conditions


logger = logging.getLogger(__name__)


class WorkflowDispatcher:
    """Dispatches a claimed event into queued workflow runs.

    Contract:
    - Receives a claimed event
    - Resolves matching definitions from provider
    - Filters inactive definitions
    - Creates one WorkflowRun per valid definition
    - Skips malformed definitions without failing whole dispatch
    - Does not claim events, execute actions, or commit
    """

    def __init__(
        self,
        db: Session,
        definition_provider: DefinitionProvider,
        run_repository: WorkflowRunRepository | None = None,
        action_repository: WorkflowActionRepository | None = None,
    ):
        self.db = db
        self.definition_provider = definition_provider
        self.run_repository = run_repository or WorkflowRunRepository(db)
        self.action_repository = action_repository or WorkflowActionRepository(db)

    def dispatch(self, event: Event) -> list[WorkflowRun]:
        """Create queued workflow runs for definitions matching the event."""
        definitions = self.definition_provider.get_definitions_for_event(
            business_id=event.business_id,
            event_type=event.event_type,
        )

        created_runs: List[WorkflowRun] = []

        for definition in definitions:
            try:
                if not definition.is_active:
                    continue

                # Evaluate conditions
                # We provide a basic context representing the event payload
                event_context = {
                    "event": {
                        "type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
                        "entity_type": event.entity_type,
                        "entity_id": str(event.entity_id),
                        "data": event.data or {}
                    }
                }
                
                conditions = definition.conditions or []
                if isinstance(conditions, dict):
                    conditions = [conditions]
                    
                if not evaluate_conditions(conditions, event_context):
                    continue

                if definition.id is None:
                    raise ValueError("Workflow definition is missing an ID")

                definition_snapshot = definition.to_snapshot()

                with self.db.begin_nested():
                    run = self.run_repository.create_from_definition(
                        db=self.db,
                        business_id=event.business_id,
                        event_id=event.id,
                        workflow_definition_id=definition.id,
                        actor_id=event.actor_id,
                        definition_snapshot=definition_snapshot,
                        workflow_id=getattr(definition, "workflow_id", None),
                    )
                    self._materialize_actions_for_run(run=run, definition=definition)
                created_runs.append(run)
            except IntegrityError:
                logger.info(
                    "Skipping duplicate workflow run for event=%s definition=%s",
                    event.id,
                    getattr(definition, "id", None),
                )
            except Exception:
                logger.warning(
                    "Skipping malformed or invalid workflow definition for event=%s definition=%s",
                    event.id,
                    getattr(definition, "id", None),
                    exc_info=True,
                )

        return created_runs

    def _materialize_actions_for_run(self, run: WorkflowRun, definition) -> None:
        """Materialize run-level action rows from definition config."""
        # Any validation/materialization failure here aborts the entire
        # definition savepoint. Definitions are all-or-nothing.
        config = definition.config or {}
        if not isinstance(config, dict):
            raise ValueError("Workflow definition config must be an object")

        raw_actions = config.get("actions", [])
        if raw_actions is None:
            raw_actions = []
        if not isinstance(raw_actions, list):
            raise ValueError("Workflow definition config.actions must be an array")

        for index, raw_action in enumerate(raw_actions):
            if not isinstance(raw_action, dict):
                raise ValueError(f"Action config at index {index} must be an object")

            action_config = parse_action_config(raw_action)
            self.action_repository.create_for_run(
                db=self.db,
                run_id=run.id,
                workflow_id=run.workflow_id,
                action_type=action_config.action_type,
                execution_order=index,
                parameters=raw_action,
                config_snapshot=action_config.model_dump(),
                continue_on_failure=action_config.continue_on_failure,
                enabled=action_config.enabled,
                timeout_seconds=action_config.timeout_seconds,
                max_attempts=action_config.retry_policy.max_attempts,
            )
