"""Operational recovery services for Celery Beat jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.enums import EventStatus, WorkflowActionStatus, WorkflowRunStatus
from app.models import Event, WorkflowAction, WorkflowRun


class EventRecoveryService:
    """Recovery operations for event processing lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    def release_stale_claims_global(self, stale_after_minutes: int = 10) -> int:
        """Release globally stale CLAIMED events back to PENDING."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
        rows_updated = (
            self.db.query(Event)
            .filter(
                Event.status == EventStatus.CLAIMED,
                Event.locked_at.is_not(None),
                Event.locked_at < cutoff,
            )
            .update(
                {
                    Event.status: EventStatus.PENDING,
                    Event.locked_at: None,
                    Event.claimed_by: None,
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        return int(rows_updated or 0)


class WorkflowActionRecoveryService:
    """Recovery operations for workflow action retries."""

    def __init__(self, db: Session):
        self.db = db

    def requeue_due_retries_global(self, as_of: datetime | None = None) -> int:
        """Move globally due retry-scheduled actions back to pending.

        For runs that receive newly pending actions, this method also moves
        run state from RUNNING back to QUEUED so the executor can claim them.
        """
        now = as_of or datetime.now(timezone.utc)
        due_run_ids = [
            run_id
            for (run_id,) in (
                self.db.query(WorkflowAction.run_id)
                .filter(
                    WorkflowAction.run_id.is_not(None),
                    WorkflowAction.enabled.is_(True),
                    WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
                    WorkflowAction.next_retry_at.is_not(None),
                    WorkflowAction.next_retry_at <= now,
                )
                .distinct()
                .all()
            )
            if run_id is not None
        ]

        rows_updated = (
            self.db.query(WorkflowAction)
            .filter(
                WorkflowAction.run_id.is_not(None),
                WorkflowAction.enabled.is_(True),
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
                WorkflowAction.next_retry_at.is_not(None),
                WorkflowAction.next_retry_at <= now,
            )
            .update(
                {
                    WorkflowAction.status: WorkflowActionStatus.PENDING,
                    WorkflowAction.next_retry_at: None,
                },
                synchronize_session=False,
            )
        )

        if due_run_ids:
            (
                self.db.query(WorkflowRun)
                .filter(
                    WorkflowRun.id.in_(due_run_ids),
                    WorkflowRun.status == WorkflowRunStatus.RUNNING,
                )
                .update(
                    {WorkflowRun.status: WorkflowRunStatus.QUEUED},
                    synchronize_session=False,
                )
            )
        self.db.flush()
        return int(rows_updated or 0)


class WorkflowRunRecoveryService:
    """Recovery operations for stale workflow runs."""

    def __init__(self, db: Session):
        self.db = db

    def release_stale_runs_global(self, stale_after_minutes: int = 30) -> int:
        """Mark globally stale RUNNING runs as FAILED."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
        rows_updated = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
                WorkflowRun.updated_at < cutoff,
            )
            .update(
                {
                    WorkflowRun.status: WorkflowRunStatus.FAILED,
                    WorkflowRun.error_message: "Run timed out - stale recovery",
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        return int(rows_updated or 0)
