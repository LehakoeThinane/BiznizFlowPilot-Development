"""Workflow executor (Phase 5 step 4: run completion and failure branching)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType, WorkflowActionStatus, WorkflowRunStatus
from app.models import Event
from app.repositories.workflow import WorkflowActionRepository, WorkflowRunRepository
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.action_handlers import ActionHandlerRegistry
from app.workflow_engine.registry import build_default_action_registry

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes materialized workflow runs.

    Phase 5 step 4 scope:
    - claim oldest QUEUED run and set it RUNNING
    - iterate enabled PENDING actions in execution order
    - dispatch handlers and apply success/failure updates
    - schedule retries for retryable action failures
    - finalize run status for completion/failure outcomes
    """

    def __init__(
        self,
        db: Session,
        run_repository: WorkflowRunRepository | None = None,
        action_repository: WorkflowActionRepository | None = None,
        handler_registry: ActionHandlerRegistry | None = None,
    ):
        self.db = db
        self.run_repository = run_repository or WorkflowRunRepository(db)
        self.action_repository = action_repository or WorkflowActionRepository(db)
        self.handler_registry = handler_registry or build_default_action_registry()

    def execute_next_run(self, business_id: UUID) -> dict[str, object]:
        """Claim one queued run and execute pending actions."""
        run = self.run_repository.claim_oldest_queued(db=self.db, business_id=business_id)
        if run is None:
            return {
                "claimed": False,
                "run_id": None,
                "run_status": None,
                "executed_action_count": 0,
                "executed_action_ids": [],
                "retry_scheduled_count": 0,
                "retry_scheduled_action_ids": [],
                "failed_action_count": 0,
                "failed_action_ids": [],
                "skipped_action_count": 0,
                "skipped_action_ids": [],
            }

        # Retries are requeued by a periodic Beat task, not inline here.
        # This loop only processes actions that are already pending.
        pending_actions = self.action_repository.get_pending_for_run(db=self.db, run_id=run.id)
        logger.info(
            "executor.run.claimed",
            extra={
                "run_id": str(run.id),
                "business_id": str(run.business_id),
                "workflow_definition_id": (
                    str(run.workflow_definition_id) if run.workflow_definition_id else None
                ),
                "event_id": str(run.event_id) if run.event_id else None,
                "action_count": len(pending_actions),
            },
        )
        context = self._build_action_context(run)

        executed_action_ids: list[str] = []
        retry_scheduled_action_ids: list[str] = []
        failed_action_ids: list[str] = []
        skipped_action_ids: list[str] = []
        run_failed = False
        for action in pending_actions:
            action_config = parse_action_config(action.config_snapshot)
            handler = self.handler_registry.get(action_config.action_type)
            attempt_started_at = datetime.now(timezone.utc)
            if action.started_at is None:
                action.started_at = attempt_started_at
            logger.info(
                "handler.action.start",
                extra={
                    "action_id": str(action.id),
                    "run_id": str(action.run_id) if action.run_id else None,
                    "business_id": str(run.business_id),
                    "action_type": action_config.action_type,
                    "attempt_count": action.attempt_count,
                },
            )
            result = handler.execute(
                db=self.db,
                action_config=action_config,
                context=context,
            )
            attempt_finished_at = datetime.now(timezone.utc)
            action.finished_at = attempt_finished_at
            action.executed_at = attempt_finished_at
            attempt_duration_ms = int((attempt_finished_at - attempt_started_at).total_seconds() * 1000)

            if result.status != "success":
                failure_type = result.failure_type or ActionFailureType.TERMINAL
                should_retry = action_config.retry_policy.should_retry(
                    failure_type=failure_type,
                    attempt_count=action.attempt_count,
                )
                if should_retry:
                    delay_seconds = self._compute_retry_delay_seconds(
                        initial_delay_seconds=action_config.retry_policy.initial_delay_seconds,
                        backoff_multiplier=action_config.retry_policy.backoff_multiplier,
                        max_delay_seconds=action_config.retry_policy.max_delay_seconds,
                        attempt_count=action.attempt_count,
                    )
                    action.status = WorkflowActionStatus.RETRY_SCHEDULED
                    action.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                    action.attempt_count = action.attempt_count + 1
                    action.result = result.model_dump()
                    action.error = result.message
                    action.failure_type = failure_type
                    retry_scheduled_action_ids.append(str(action.id))
                    logger.info(
                        "handler.action.failed",
                        extra={
                            "action_id": str(action.id),
                            "run_id": str(action.run_id) if action.run_id else None,
                            "business_id": str(run.business_id),
                            "action_type": action_config.action_type,
                            "result_status": result.status,
                            "failure_type": failure_type.value,
                            "duration_ms": attempt_duration_ms,
                            "will_retry": True,
                        },
                    )
                    continue

                action.result = result.model_dump()
                action.error = result.message
                action.failure_type = failure_type

                if failure_type == ActionFailureType.SKIPPABLE:
                    action.status = WorkflowActionStatus.SKIPPED
                    skipped_action_ids.append(str(action.id))
                    logger.info(
                        "handler.action.failed",
                        extra={
                            "action_id": str(action.id),
                            "run_id": str(action.run_id) if action.run_id else None,
                            "business_id": str(run.business_id),
                            "action_type": action_config.action_type,
                            "result_status": result.status,
                            "failure_type": failure_type.value,
                            "duration_ms": attempt_duration_ms,
                            "will_retry": False,
                        },
                    )
                    continue

                action.status = WorkflowActionStatus.FAILED
                failed_action_ids.append(str(action.id))
                logger.info(
                    "handler.action.failed",
                    extra={
                        "action_id": str(action.id),
                        "run_id": str(action.run_id) if action.run_id else None,
                        "business_id": str(run.business_id),
                        "action_type": action_config.action_type,
                        "result_status": result.status,
                        "failure_type": failure_type.value,
                        "duration_ms": attempt_duration_ms,
                        "will_retry": False,
                    },
                )

                if action_config.continue_on_failure:
                    continue

                run.status = WorkflowRunStatus.FAILED
                run.error_message = result.message
                run_failed = True
                break

            action.status = WorkflowActionStatus.COMPLETED
            action.result = result.model_dump()
            action.error = None
            action.failure_type = None
            executed_action_ids.append(str(action.id))
            logger.info(
                "handler.action.complete",
                extra={
                    "action_id": str(action.id),
                    "run_id": str(action.run_id) if action.run_id else None,
                    "business_id": str(run.business_id),
                    "action_type": action_config.action_type,
                    "result_status": result.status,
                    "failure_type": None,
                    "duration_ms": attempt_duration_ms,
                    "will_retry": False,
                },
            )

        # Session autoflush is disabled in tests; flush before status resolution.
        self.db.flush()
        if not run_failed:
            if retry_scheduled_action_ids or self.action_repository.has_retry_scheduled_for_run(
                db=self.db,
                run_id=run.id,
            ):
                # Keep run in running state while waiting for retries.
                run.status = WorkflowRunStatus.RUNNING
            else:
                remaining_actions = self.action_repository.get_pending_for_run(db=self.db, run_id=run.id)
                # All actions are either COMPLETED, FAILED (continue_on_failure),
                # or SKIPPED, and there are no retries pending. Run is done.
                if not remaining_actions:
                    run.status = WorkflowRunStatus.COMPLETED

        if run.status in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED):
            finished_at = datetime.now(timezone.utc)
            run.finished_at = finished_at
            duration_ms: int | None = None
            if run.started_at:
                started_at = run.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            logger.info(
                "executor.run.completed" if run.status == WorkflowRunStatus.COMPLETED else "executor.run.failed",
                extra={
                    "run_id": str(run.id),
                    "business_id": str(run.business_id),
                    "duration_ms": duration_ms,
                    "actions_executed": len(executed_action_ids),
                    "actions_failed": len(failed_action_ids),
                    "actions_retried": len(retry_scheduled_action_ids),
                    "final_status": run.status.value,
                },
            )

        self.db.flush()
        return {
            "claimed": True,
            "run_id": str(run.id),
            "run_status": run.status.value,
            "executed_action_count": len(executed_action_ids),
            "executed_action_ids": executed_action_ids,
            "retry_scheduled_count": len(retry_scheduled_action_ids),
            "retry_scheduled_action_ids": retry_scheduled_action_ids,
            "failed_action_count": len(failed_action_ids),
            "failed_action_ids": failed_action_ids,
            "skipped_action_count": len(skipped_action_ids),
            "skipped_action_ids": skipped_action_ids,
        }

    def _build_action_context(self, run) -> dict[str, Any]:
        """Build per-run context passed to action handlers."""
        event: Event | None = None
        if run.event_id:
            event = (
                self.db.query(Event)
                .filter(
                    Event.id == run.event_id,
                    Event.business_id == run.business_id,
                )
                .first()
            )
        return {
            "run_id": str(run.id),
            "business_id": str(run.business_id),
            "event_id": str(run.event_id) if run.event_id else None,
            "entity_type": event.entity_type if event else None,
            "entity_id": str(event.entity_id) if event and event.entity_id else None,
            "actor_id": str(run.actor_id) if run.actor_id else None,
            "workflow_definition_id": (
                str(run.workflow_definition_id) if run.workflow_definition_id else None
            ),
            "definition_snapshot": run.definition_snapshot or {},
        }

    @staticmethod
    def _compute_retry_delay_seconds(
        *,
        initial_delay_seconds: int,
        backoff_multiplier: float,
        max_delay_seconds: int,
        attempt_count: int,
    ) -> int:
        """Compute exponential backoff delay capped by max_delay_seconds."""
        raw_delay = float(initial_delay_seconds) * (backoff_multiplier ** attempt_count)
        return int(min(max_delay_seconds, max(1.0, raw_delay)))
