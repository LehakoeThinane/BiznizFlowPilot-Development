"""Tests for Phase 7 recovery services, tasks, and Beat schedule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.enums import EventStatus, EventType, WorkflowActionStatus, WorkflowRunStatus
from app.core.config import settings
from app.models import Event, WorkflowAction, WorkflowRun
from app.workers import recovery as recovery_tasks
from app.workers.celery_app import celery_app


class _FixedSessionContext:
    """Context manager wrapper that returns a provided SQLAlchemy session."""

    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False


def _patch_sessionlocal(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(
        recovery_tasks,
        "SessionLocal",
        lambda: _FixedSessionContext(session),
    )


def test_release_stale_event_claims_task_idempotent(
    test_db: Session,
    owner_business,
    other_business,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime.now(timezone.utc)
    stale_owner = Event(
        business_id=owner_business.id,
        event_type=EventType.LEAD_CREATED,
        entity_type="lead",
        entity_id=uuid4(),
        status=EventStatus.CLAIMED,
        locked_at=now - timedelta(minutes=20),
        claimed_by="worker-1",
    )
    stale_other = Event(
        business_id=other_business.id,
        event_type=EventType.TASK_CREATED,
        entity_type="task",
        entity_id=uuid4(),
        status=EventStatus.CLAIMED,
        locked_at=now - timedelta(minutes=15),
        claimed_by="worker-2",
    )
    fresh_claimed = Event(
        business_id=owner_business.id,
        event_type=EventType.TASK_ASSIGNED,
        entity_type="task",
        entity_id=uuid4(),
        status=EventStatus.CLAIMED,
        locked_at=now - timedelta(minutes=2),
        claimed_by="worker-3",
    )
    test_db.add_all([stale_owner, stale_other, fresh_claimed])
    test_db.commit()

    _patch_sessionlocal(monkeypatch, test_db)
    result = recovery_tasks.release_stale_event_claims_task.run(stale_after_minutes=10)
    assert result == {"status": "ok", "rows_affected": 2}

    test_db.refresh(stale_owner)
    test_db.refresh(stale_other)
    test_db.refresh(fresh_claimed)

    assert stale_owner.status == EventStatus.PENDING
    assert stale_owner.locked_at is None
    assert stale_owner.claimed_by is None
    assert stale_other.status == EventStatus.PENDING
    assert fresh_claimed.status == EventStatus.CLAIMED

    rerun = recovery_tasks.release_stale_event_claims_task.run(stale_after_minutes=10)
    assert rerun == {"status": "ok", "rows_affected": 0}


def test_requeue_due_action_retries_task_idempotent(
    test_db: Session,
    owner_business,
    other_business,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime.now(timezone.utc)
    run_owner = WorkflowRun(
        business_id=owner_business.id,
        status=WorkflowRunStatus.RUNNING,
        definition_snapshot={},
    )
    run_other = WorkflowRun(
        business_id=other_business.id,
        status=WorkflowRunStatus.RUNNING,
        definition_snapshot={},
    )
    unaffected_running = WorkflowRun(
        business_id=owner_business.id,
        status=WorkflowRunStatus.RUNNING,
        definition_snapshot={},
    )
    test_db.add_all([run_owner, run_other, unaffected_running])
    test_db.flush()

    due_owner = WorkflowAction(
        run_id=run_owner.id,
        action_type="log",
        status=WorkflowActionStatus.RETRY_SCHEDULED,
        next_retry_at=now - timedelta(minutes=1),
        enabled=True,
        config_snapshot={"action_type": "log", "message": "due-owner"},
    )
    due_other = WorkflowAction(
        run_id=run_other.id,
        action_type="log",
        status=WorkflowActionStatus.RETRY_SCHEDULED,
        next_retry_at=now - timedelta(minutes=1),
        enabled=True,
        config_snapshot={"action_type": "log", "message": "due-other"},
    )
    not_due = WorkflowAction(
        run_id=run_owner.id,
        action_type="log",
        status=WorkflowActionStatus.RETRY_SCHEDULED,
        next_retry_at=now + timedelta(minutes=5),
        enabled=True,
        config_snapshot={"action_type": "log", "message": "future"},
    )
    disabled_due = WorkflowAction(
        run_id=run_owner.id,
        action_type="log",
        status=WorkflowActionStatus.RETRY_SCHEDULED,
        next_retry_at=now - timedelta(minutes=1),
        enabled=False,
        config_snapshot={"action_type": "log", "message": "disabled"},
    )
    test_db.add_all([due_owner, due_other, not_due, disabled_due])
    test_db.commit()

    _patch_sessionlocal(monkeypatch, test_db)
    result = recovery_tasks.requeue_due_action_retries_task.run()
    assert result == {"status": "ok", "rows_affected": 2}

    test_db.refresh(due_owner)
    test_db.refresh(due_other)
    test_db.refresh(not_due)
    test_db.refresh(disabled_due)
    test_db.refresh(run_owner)
    test_db.refresh(run_other)
    test_db.refresh(unaffected_running)

    assert due_owner.status == WorkflowActionStatus.PENDING
    assert due_owner.next_retry_at is None
    assert due_other.status == WorkflowActionStatus.PENDING
    assert not_due.status == WorkflowActionStatus.RETRY_SCHEDULED
    assert disabled_due.status == WorkflowActionStatus.RETRY_SCHEDULED
    assert run_owner.status == WorkflowRunStatus.QUEUED
    assert run_other.status == WorkflowRunStatus.QUEUED
    assert unaffected_running.status == WorkflowRunStatus.RUNNING

    rerun = recovery_tasks.requeue_due_action_retries_task.run()
    assert rerun == {"status": "ok", "rows_affected": 0}


def test_release_stale_workflow_runs_task_idempotent(
    test_db: Session,
    owner_business,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime.now(timezone.utc)
    stale_run = WorkflowRun(
        business_id=owner_business.id,
        status=WorkflowRunStatus.RUNNING,
        definition_snapshot={},
        updated_at=now - timedelta(minutes=50),
    )
    fresh_run = WorkflowRun(
        business_id=owner_business.id,
        status=WorkflowRunStatus.RUNNING,
        definition_snapshot={},
        updated_at=now - timedelta(minutes=5),
    )
    completed_run = WorkflowRun(
        business_id=owner_business.id,
        status=WorkflowRunStatus.COMPLETED,
        definition_snapshot={},
        updated_at=now - timedelta(minutes=90),
    )
    test_db.add_all([stale_run, fresh_run, completed_run])
    test_db.commit()

    _patch_sessionlocal(monkeypatch, test_db)
    result = recovery_tasks.release_stale_workflow_runs_task.run(stale_after_minutes=30)
    assert result == {"status": "ok", "rows_affected": 1}

    test_db.refresh(stale_run)
    test_db.refresh(fresh_run)
    test_db.refresh(completed_run)

    assert stale_run.status == WorkflowRunStatus.FAILED
    assert stale_run.error_message == "Run timed out - stale recovery"
    assert fresh_run.status == WorkflowRunStatus.RUNNING
    assert completed_run.status == WorkflowRunStatus.COMPLETED

    rerun = recovery_tasks.release_stale_workflow_runs_task.run(stale_after_minutes=30)
    assert rerun == {"status": "ok", "rows_affected": 0}


def test_recovery_task_rollback_and_reraise_on_failure(monkeypatch: pytest.MonkeyPatch):
    class _FakeSession:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

    fake_session = _FakeSession()
    monkeypatch.setattr(
        recovery_tasks,
        "SessionLocal",
        lambda: _FixedSessionContext(fake_session),  # type: ignore[arg-type]
    )

    def _boom(self, stale_after_minutes: int = 10) -> int:
        _ = stale_after_minutes
        raise RuntimeError("forced failure")

    monkeypatch.setattr(
        recovery_tasks.EventRecoveryService,
        "release_stale_claims_global",
        _boom,
    )

    with pytest.raises(RuntimeError, match="forced failure"):
        recovery_tasks.release_stale_event_claims_task.run(stale_after_minutes=10)

    assert fake_session.commits == 0
    assert fake_session.rollbacks == 1


def test_beat_schedule_contains_recovery_jobs():
    schedule = celery_app.conf.beat_schedule

    assert "release-stale-event-claims" in schedule
    assert schedule["release-stale-event-claims"]["task"] == "ops.release_stale_event_claims"
    assert int(schedule["release-stale-event-claims"]["schedule"].total_seconds()) == settings.stale_claim_check_interval_seconds

    assert "requeue-due-action-retries" in schedule
    assert schedule["requeue-due-action-retries"]["task"] == "ops.requeue_due_action_retries"
    assert int(schedule["requeue-due-action-retries"]["schedule"].total_seconds()) == settings.action_retry_check_interval_seconds

    assert "release-stale-workflow-runs" in schedule
    assert schedule["release-stale-workflow-runs"]["task"] == "ops.release_stale_workflow_runs"
    assert int(schedule["release-stale-workflow-runs"]["schedule"].total_seconds()) == settings.stale_run_check_interval_seconds
