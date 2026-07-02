"""Workflow repositories for data access."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import WorkflowActionStatus, WorkflowRunStatus, EventType
from app.models import Workflow, WorkflowAction, WorkflowDefinition, WorkflowRun
from app.repositories.base import BaseRepository


def _normalize_run_status(value: WorkflowRunStatus | str) -> WorkflowRunStatus:
    """Support legacy status names while moving to the phase-4 lifecycle."""
    if isinstance(value, WorkflowRunStatus):
        return value

    normalized = value.lower().strip()
    legacy_map = {
        "pending": WorkflowRunStatus.QUEUED,
        "success": WorkflowRunStatus.COMPLETED,
    }
    if normalized in legacy_map:
        return legacy_map[normalized]

    return WorkflowRunStatus(normalized)


class WorkflowRepository(BaseRepository[Workflow]):
    """Workflow repository with multi-tenant enforcement."""

    def __init__(self, db: Session):
        super().__init__(db, Workflow)

    def _session(self, db: Session | None) -> Session:
        return db or self.db

    def get(self, db: Session | None, business_id: UUID, workflow_id: UUID) -> Optional[Workflow]:
        session = self._session(db)
        return (
            session.query(Workflow)
            .filter(
                Workflow.business_id == business_id,
                Workflow.id == workflow_id,
            )
            .first()
        )

    def list(self, db: Session | None, business_id: UUID, skip: int = 0, limit: int = 100) -> List[Workflow]:
        session = self._session(db)
        return (
            session.query(Workflow)
            .filter(Workflow.business_id == business_id)
            .order_by(Workflow.order.asc(), Workflow.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_event_type(self, db: Session | None, business_id: UUID, event_type: str) -> List[Workflow]:
        session = self._session(db)
        return (
            session.query(Workflow)
            .filter(
                Workflow.business_id == business_id,
                Workflow.trigger_event_type == event_type,
                Workflow.enabled.is_(True),
            )
            .order_by(Workflow.order.asc())
            .all()
        )

    def get_all_enabled(self, db: Session | None, business_id: UUID) -> List[Workflow]:
        session = self._session(db)
        return (
            session.query(Workflow)
            .filter(
                Workflow.business_id == business_id,
                Workflow.enabled.is_(True),
            )
            .order_by(Workflow.order.asc())
            .all()
        )

    def toggle_enabled(
        self,
        db: Session | None,
        business_id: UUID,
        workflow_id: UUID,
        enabled: bool,
    ) -> Optional[Workflow]:
        session = self._session(db)
        workflow = self.get(session, business_id, workflow_id)
        if workflow is None:
            return None

        workflow.enabled = enabled
        session.commit()
        session.refresh(workflow)
        return workflow


class WorkflowDefinitionRepository(BaseRepository[WorkflowDefinition]):
    """Workflow definition repository for dispatcher matching."""

    def __init__(self, db: Session):
        super().__init__(db, WorkflowDefinition)

    def _session(self, db: Session | None) -> Session:
        return db or self.db

    def _base_query(
        self,
        session: Session,
        business_id: UUID,
        *,
        include_deleted: bool = False,
    ):
        query = session.query(WorkflowDefinition).filter(
            WorkflowDefinition.business_id == business_id,
        )
        if not include_deleted:
            query = query.filter(WorkflowDefinition.deleted_at.is_(None))
        return query

    def get(
        self,
        db: Session | None,
        business_id: UUID,
        definition_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> WorkflowDefinition | None:
        session = self._session(db)
        return (
            self._base_query(session, business_id, include_deleted=include_deleted)
            .filter(WorkflowDefinition.id == definition_id)
            .first()
        )

    def list(
        self,
        db: Session | None,
        business_id: UUID,
        *,
        event_type: EventType | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkflowDefinition]:
        session = self._session(db)
        query = self._base_query(session, business_id)
        if event_type is not None:
            query = query.filter(WorkflowDefinition.event_type == event_type)
        if is_active is not None:
            query = query.filter(WorkflowDefinition.is_active.is_(is_active))
        return (
            query.order_by(WorkflowDefinition.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session | None,
        business_id: UUID,
        *,
        event_type: EventType | None = None,
        is_active: bool | None = None,
    ) -> int:
        session = self._session(db)
        query = self._base_query(session, business_id)
        if event_type is not None:
            query = query.filter(WorkflowDefinition.event_type == event_type)
        if is_active is not None:
            query = query.filter(WorkflowDefinition.is_active.is_(is_active))
        return query.count()

    def get_definitions_for_event(
        self,
        db: Session | None,
        business_id: UUID,
        event_type: EventType,
    ) -> List[WorkflowDefinition]:
        session = self._session(db)
        return (
            self._base_query(session, business_id)
            .filter(
                WorkflowDefinition.event_type == event_type,
                WorkflowDefinition.is_active.is_(True),
            )
            .order_by(WorkflowDefinition.created_at.asc())
            .all()
        )

    def create_definition(
        self,
        db: Session | None,
        *,
        business_id: UUID,
        event_type: EventType,
        is_active: bool,
        name: str,
        conditions: dict[str, Any],
        config: dict[str, Any],
        workflow_id: UUID | None = None,
    ) -> WorkflowDefinition:
        session = self._session(db)
        definition = WorkflowDefinition(
            business_id=business_id,
            event_type=event_type,
            is_active=is_active,
            name=name,
            conditions=conditions,
            config=config,
            workflow_id=workflow_id,
            deleted_at=None,
        )
        session.add(definition)
        session.flush()
        return definition

    def update_definition(
        self,
        db: Session | None,
        *,
        business_id: UUID,
        definition_id: UUID,
        **updates: Any,
    ) -> WorkflowDefinition | None:
        definition = self.get(db, business_id, definition_id)
        if definition is None:
            return None

        allowed_fields = {"name", "is_active", "config"}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            invalid_csv = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Unsupported workflow definition update fields: {invalid_csv}")

        for field in allowed_fields:
            if field in updates:
                setattr(definition, field, updates[field])
        self._session(db).flush()
        return definition

    def soft_delete(
        self,
        db: Session | None,
        *,
        business_id: UUID,
        definition_id: UUID,
        deleted_at: datetime | None = None,
    ) -> WorkflowDefinition | None:
        definition = self.get(db, business_id, definition_id)
        if definition is None:
            return None

        definition.deleted_at = deleted_at or datetime.now(timezone.utc)
        definition.is_active = False
        self._session(db).flush()
        return definition


class WorkflowActionRepository(BaseRepository[WorkflowAction]):
    """Workflow action repository."""

    def __init__(self, db: Session):
        super().__init__(db, WorkflowAction)

    def _session(self, db: Session | None) -> Session:
        return db or self.db

    def get_by_workflow(
        self,
        db_or_workflow_id: Session | UUID,
        workflow_id: UUID | None = None,
    ) -> List[WorkflowAction]:
        """Get actions by workflow.

        Supports both call styles:
        - get_by_workflow(db, workflow_id)
        - get_by_workflow(workflow_id)
        """
        if workflow_id is None:
            session = self.db
            workflow_id = db_or_workflow_id  # type: ignore[assignment]
        else:
            session = db_or_workflow_id  # type: ignore[assignment]

        return (
            session.query(WorkflowAction)
            .filter(WorkflowAction.workflow_id == workflow_id)
            .order_by(WorkflowAction.order.asc())
            .all()
        )

    def delete_by_workflow(self, db: Session | None, workflow_id: UUID) -> int:
        session = self._session(db)
        deleted = session.query(WorkflowAction).filter(WorkflowAction.workflow_id == workflow_id).delete()
        session.commit()
        return int(deleted or 0)

    def get_by_run(self, db: Session | None, run_id: UUID) -> List[WorkflowAction]:
        """Get materialized actions for a run in execution order."""
        session = self._session(db)
        return (
            session.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run_id)
            .order_by(WorkflowAction.execution_order.asc(), WorkflowAction.created_at.asc())
            .all()
        )

    def get_pending_for_run(self, db: Session, run_id: UUID) -> List[WorkflowAction]:
        """Get enabled pending actions for a run in execution order.

        `created_at` is a defensive tie-breaker only. Under normal dispatch
        materialization, execution_order is unique per run.
        """
        return (
            db.query(WorkflowAction)
            .filter(
                WorkflowAction.run_id == run_id,
                WorkflowAction.enabled.is_(True),
                WorkflowAction.status == WorkflowActionStatus.PENDING,
            )
            .order_by(WorkflowAction.execution_order.asc(), WorkflowAction.created_at.asc())
            .all()
        )

    def requeue_due_retries(self, db: Session, run_id: UUID, as_of: datetime | None = None) -> int:
        """Move due retry-scheduled actions back to pending for execution."""
        now = as_of or datetime.now(timezone.utc)
        rows_updated = (
            db.query(WorkflowAction)
            .filter(
                WorkflowAction.run_id == run_id,
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
        db.flush()
        return int(rows_updated or 0)

    def has_retry_scheduled_for_run(self, db: Session, run_id: UUID) -> bool:
        """Check whether a run still has enabled actions waiting on retry."""
        return (
            db.query(WorkflowAction)
            .filter(
                WorkflowAction.run_id == run_id,
                WorkflowAction.enabled.is_(True),
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
            )
            .first()
            is not None
        )

    def requeue_due_retries_for_business(
        self,
        db: Session,
        business_id: UUID,
        as_of: datetime | None = None,
    ) -> int:
        """Move due retry-scheduled actions to pending for all runs in a business."""
        now = as_of or datetime.now(timezone.utc)
        due_action_ids = [
            action_id
            for (action_id,) in (
                db.query(WorkflowAction.id)
                .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
                .filter(
                    WorkflowRun.business_id == business_id,
                    WorkflowAction.enabled.is_(True),
                    WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
                    WorkflowAction.next_retry_at.is_not(None),
                    WorkflowAction.next_retry_at <= now,
                )
                .all()
            )
        ]
        if not due_action_ids:
            return 0

        (
            db.query(WorkflowAction)
            .filter(WorkflowAction.id.in_(due_action_ids))
            .update(
                {
                    WorkflowAction.status: WorkflowActionStatus.PENDING,
                    WorkflowAction.next_retry_at: None,
                },
                synchronize_session=False,
            )
        )
        db.flush()
        return len(due_action_ids)

    def create_for_run(
        self,
        db: Session,
        *,
        run_id: UUID,
        workflow_id: UUID | None,
        action_type: str,
        execution_order: int,
        config_snapshot: dict[str, Any],
        parameters: dict[str, Any] | None = None,
        continue_on_failure: bool = False,
        enabled: bool = True,
        timeout_seconds: int | None = None,
        max_attempts: int = 0,
    ) -> WorkflowAction:
        """Materialize one workflow action row for a run without committing."""
        session = db
        action = WorkflowAction(
            run_id=run_id,
            workflow_id=workflow_id,
            action_type=action_type,
            parameters=parameters or {},
            order=execution_order,
            execution_order=execution_order,
            status=WorkflowActionStatus.PENDING,
            result={},
            error=None,
            failure_type=None,
            attempt_count=0,
            max_attempts=max_attempts,
            next_retry_at=None,
            continue_on_failure=continue_on_failure,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            config_snapshot=config_snapshot,
        )
        session.add(action)
        session.flush()
        return action


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    """Workflow run repository with multi-tenant enforcement."""

    def __init__(self, db: Session):
        super().__init__(db, WorkflowRun)

    def _session(self, db: Session | None) -> Session:
        return db or self.db

    def get(self, db: Session | None, business_id: UUID, run_id: UUID) -> Optional[WorkflowRun]:
        session = self._session(db)
        return (
            session.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.id == run_id,
            )
            .first()
        )

    def list(self, db: Session | None, business_id: UUID, skip: int = 0, limit: int = 100) -> List[WorkflowRun]:
        session = self._session(db)
        return (
            session.query(WorkflowRun)
            .filter(WorkflowRun.business_id == business_id)
            .order_by(WorkflowRun.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_workflow(
        self,
        db: Session | None,
        business_id: UUID,
        workflow_id: UUID,
        limit: int = 100,
    ) -> List[WorkflowRun]:
        session = self._session(db)
        return (
            session.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.workflow_id == workflow_id,
            )
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_status(
        self,
        db: Session | None,
        business_id: UUID,
        status: WorkflowRunStatus | str,
        limit: int = 100,
    ) -> List[WorkflowRun]:
        session = self._session(db)
        normalized = _normalize_run_status(status)
        return (
            session.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == normalized,
            )
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_pending(self, db: Session | None, business_id: UUID) -> List[WorkflowRun]:
        return self.get_by_status(db, business_id, WorkflowRunStatus.QUEUED)

    def get_failed(self, db: Session | None, business_id: UUID, limit: int = 100) -> List[WorkflowRun]:
        return self.get_by_status(db, business_id, WorkflowRunStatus.FAILED, limit)

    def claim_oldest_queued(self, db: Session, business_id: UUID) -> WorkflowRun | None:
        """Claim the oldest queued run for execution.

        Caller owns transaction boundaries and commit/rollback.
        Note: skip_locked behavior is exercised in PostgreSQL. SQLite-based
        tests validate query shape, not lock semantics.
        """
        run = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
                WorkflowRun.status == WorkflowRunStatus.QUEUED,
            )
            .order_by(WorkflowRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if run is None:
            return None

        now = datetime.now(timezone.utc)
        run.status = WorkflowRunStatus.RUNNING
        # Preserve first-claim timestamp to measure full run wall time
        # across retries/requeues.
        if run.started_at is None:
            run.started_at = now
        run.finished_at = None
        db.flush()
        return run

    def release_stale_runs(
        self,
        db: Session,
        business_id: UUID,
        stale_after_minutes: int = 30,
    ) -> int:
        """Mark stale RUNNING runs as failed for operational recovery.

        Caller owns transaction boundaries and commit/rollback.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
        rows_updated = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business_id,
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
        db.flush()
        return int(rows_updated or 0)

    def create_from_definition(
        self,
        db: Session | None,
        *,
        business_id: UUID,
        event_id: UUID,
        workflow_definition_id: UUID,
        actor_id: UUID | None,
        definition_snapshot: dict[str, Any],
        workflow_id: UUID | None = None,
        status: WorkflowRunStatus = WorkflowRunStatus.QUEUED,
    ) -> WorkflowRun:
        """Create a workflow run without committing transaction boundaries."""
        session = self._session(db)
        run = WorkflowRun(
            workflow_id=workflow_id,
            workflow_definition_id=workflow_definition_id,
            business_id=business_id,
            event_id=event_id,
            actor_id=actor_id,
            status=status,
            definition_snapshot=definition_snapshot,
            results={},
        )
        session.add(run)
        session.flush()
        return run
