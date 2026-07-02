"""Operational metrics service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import WorkflowActionStatus, WorkflowRunStatus
from app.models import WorkflowAction, WorkflowDefinition, WorkflowRun
from app.schemas.metrics import (
    MetricsResponse,
    WorkflowActionMetrics,
    WorkflowDefinitionMetrics,
    WorkflowRunMetrics,
)


class MetricsService:
    """Build aggregate platform metrics for one tenant."""

    def __init__(self, db: Session):
        self.db = db

    def get_metrics(self, business_id: UUID) -> MetricsResponse:
        """Return workflow run/action/definition aggregates for one tenant."""
        runs_total = (
            self.db.query(WorkflowRun)
            .filter(WorkflowRun.business_id == business_id)
            .count()
        )
        runs_completed = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.COMPLETED,
            )
            .count()
        )
        runs_failed = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.FAILED,
            )
            .count()
        )
        runs_running = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )

        action_base_query = (
            self.db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(WorkflowRun.business_id == business_id)
        )
        actions_total = action_base_query.count()
        actions_completed = (
            action_base_query.filter(WorkflowAction.status == WorkflowActionStatus.COMPLETED)
            .count()
        )
        actions_failed = (
            action_base_query.filter(WorkflowAction.status == WorkflowActionStatus.FAILED)
            .count()
        )
        actions_retry_scheduled = (
            action_base_query.filter(WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED)
            .count()
        )

        definitions_total = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.deleted_at.is_(None),
            )
            .count()
        )
        definitions_active = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.deleted_at.is_(None),
                WorkflowDefinition.is_active.is_(True),
            )
            .count()
        )

        return MetricsResponse(
            business_id=business_id,
            runs=WorkflowRunMetrics(
                total=runs_total,
                completed=runs_completed,
                failed=runs_failed,
                running=runs_running,
            ),
            actions=WorkflowActionMetrics(
                total=actions_total,
                completed=actions_completed,
                failed=actions_failed,
                retry_scheduled=actions_retry_scheduled,
            ),
            definitions=WorkflowDefinitionMetrics(
                total=definitions_total,
                active=definitions_active,
            ),
        )

