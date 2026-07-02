"""Recovery load tests for stale claims, stale runs, and due retries."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.enums import EventStatus, EventType, WorkflowActionStatus, WorkflowRunStatus
from app.models import Event, WorkflowAction, WorkflowRun
from app.services.recovery import (
    EventRecoveryService,
    WorkflowActionRecoveryService,
    WorkflowRunRecoveryService,
)

from .utils import create_business


class TestWorkflowRecoveryLoad:
    def test_release_stale_claims_at_scale(self, load_db):
        """Seed 500 stale CLAIMED events and verify global release behavior."""
        db, created_business_ids = load_db
        tenant = create_business(db, label="load-recovery-events")
        created_business_ids.append(tenant.id)

        stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        fresh_lock = datetime.now(timezone.utc) - timedelta(minutes=2)

        stale_count = 500
        fresh_count = 40

        db.add_all(
            [
                Event(
                    business_id=tenant.id,
                    event_type=EventType.LEAD_CREATED,
                    entity_type="lead",
                    entity_id=uuid4(),
                    status=EventStatus.CLAIMED,
                    locked_at=stale_cutoff,
                    claimed_by="worker-stale",
                )
                for _ in range(stale_count)
            ]
        )
        db.add_all(
            [
                Event(
                    business_id=tenant.id,
                    event_type=EventType.LEAD_CREATED,
                    entity_type="lead",
                    entity_id=uuid4(),
                    status=EventStatus.CLAIMED,
                    locked_at=fresh_lock,
                    claimed_by="worker-fresh",
                )
                for _ in range(fresh_count)
            ]
        )
        db.commit()

        started_at = time.perf_counter()
        released = EventRecoveryService(db).release_stale_claims_global(stale_after_minutes=30)
        db.commit()
        elapsed_seconds = time.perf_counter() - started_at

        assert released == stale_count
        assert elapsed_seconds < 5.0

        pending_count = (
            db.query(Event)
            .filter(
                Event.business_id == tenant.id,
                Event.status == EventStatus.PENDING,
                Event.claimed_by.is_(None),
                Event.locked_at.is_(None),
            )
            .count()
        )
        still_claimed_fresh = (
            db.query(Event)
            .filter(
                Event.business_id == tenant.id,
                Event.status == EventStatus.CLAIMED,
                Event.claimed_by == "worker-fresh",
            )
            .count()
        )

        assert pending_count == stale_count
        assert still_claimed_fresh == fresh_count

    def test_release_stale_runs_at_scale(self, load_db):
        """Seed 200 stale RUNNING runs and verify stale-run recovery speed."""
        db, created_business_ids = load_db
        tenant = create_business(db, label="load-recovery-runs")
        created_business_ids.append(tenant.id)

        stale_updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
        fresh_updated_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        stale_count = 200
        fresh_count = 30

        db.add_all(
            [
                WorkflowRun(
                    business_id=tenant.id,
                    status=WorkflowRunStatus.RUNNING,
                    definition_snapshot={},
                    results={},
                    updated_at=stale_updated_at,
                )
                for _ in range(stale_count)
            ]
        )
        db.add_all(
            [
                WorkflowRun(
                    business_id=tenant.id,
                    status=WorkflowRunStatus.RUNNING,
                    definition_snapshot={},
                    results={},
                    updated_at=fresh_updated_at,
                )
                for _ in range(fresh_count)
            ]
        )
        db.commit()

        started_at = time.perf_counter()
        marked_failed = WorkflowRunRecoveryService(db).release_stale_runs_global(stale_after_minutes=30)
        db.commit()
        elapsed_seconds = time.perf_counter() - started_at

        assert marked_failed == stale_count
        assert elapsed_seconds < 5.0

        failed_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowRun.status == WorkflowRunStatus.FAILED,
                WorkflowRun.error_message == "Run timed out - stale recovery",
            )
            .count()
        )
        still_running = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )

        assert failed_runs == stale_count
        assert still_running == fresh_count

    def test_requeue_due_retries_at_scale(self, load_db):
        """Seed 300 due retries and verify requeue + run-state reset behavior."""
        db, created_business_ids = load_db
        tenant = create_business(db, label="load-recovery-retries")
        created_business_ids.append(tenant.id)

        due_count = 300
        not_due_count = 25
        disabled_due_count = 15
        past_due = datetime.now(timezone.utc) - timedelta(minutes=10)
        future_due = datetime.now(timezone.utc) + timedelta(minutes=10)

        due_runs: list[WorkflowRun] = []
        for _ in range(due_count):
            run = WorkflowRun(
                business_id=tenant.id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
            )
            db.add(run)
            due_runs.append(run)
        db.flush()

        db.add_all(
            [
                WorkflowAction(
                    run_id=run.id,
                    action_type="webhook",
                    parameters={},
                    execution_order=0,
                    status=WorkflowActionStatus.RETRY_SCHEDULED,
                    next_retry_at=past_due,
                    enabled=True,
                )
                for run in due_runs
            ]
        )

        not_due_runs: list[WorkflowRun] = []
        for _ in range(not_due_count):
            run = WorkflowRun(
                business_id=tenant.id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
            )
            db.add(run)
            not_due_runs.append(run)
        db.flush()
        db.add_all(
            [
                WorkflowAction(
                    run_id=run.id,
                    action_type="webhook",
                    parameters={},
                    execution_order=0,
                    status=WorkflowActionStatus.RETRY_SCHEDULED,
                    next_retry_at=future_due,
                    enabled=True,
                )
                for run in not_due_runs
            ]
        )

        disabled_due_runs: list[WorkflowRun] = []
        for _ in range(disabled_due_count):
            run = WorkflowRun(
                business_id=tenant.id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
            )
            db.add(run)
            disabled_due_runs.append(run)
        db.flush()
        db.add_all(
            [
                WorkflowAction(
                    run_id=run.id,
                    action_type="webhook",
                    parameters={},
                    execution_order=0,
                    status=WorkflowActionStatus.RETRY_SCHEDULED,
                    next_retry_at=past_due,
                    enabled=False,
                )
                for run in disabled_due_runs
            ]
        )
        db.commit()

        started_at = time.perf_counter()
        requeued = WorkflowActionRecoveryService(db).requeue_due_retries_global()
        db.commit()
        elapsed_seconds = time.perf_counter() - started_at

        assert requeued == due_count
        assert elapsed_seconds < 5.0

        due_pending = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowAction.enabled.is_(True),
                WorkflowAction.status == WorkflowActionStatus.PENDING,
                WorkflowAction.next_retry_at.is_(None),
            )
            .count()
        )
        still_retry_scheduled = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
            )
            .count()
        )
        queued_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowRun.status == WorkflowRunStatus.QUEUED,
            )
            .count()
        )
        still_running_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )

        assert due_pending == due_count
        assert still_retry_scheduled == not_due_count + disabled_due_count
        assert queued_runs == due_count
        assert still_running_runs == not_due_count + disabled_due_count

    def test_recovery_tasks_respect_tenant_boundaries(self, load_db):
        """Verify global recovery tasks process all tenants without cross-tenant pollution."""
        db, created_business_ids = load_db
        tenant_a = create_business(db, label="tenant-a")
        tenant_b = create_business(db, label="tenant-b")
        tenant_c = create_business(db, label="tenant-c")
        created_business_ids.extend([tenant_a.id, tenant_b.id, tenant_c.id])

        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(hours=2)
        future_time = now + timedelta(minutes=10)

        # Tenant A: stale event claims only (plus one fresh claim and one not-due retry).
        db.add_all(
            [
                Event(
                    business_id=tenant_a.id,
                    event_type=EventType.LEAD_CREATED,
                    entity_type="lead",
                    entity_id=uuid4(),
                    status=EventStatus.CLAIMED,
                    locked_at=stale_time,
                    claimed_by="tenant-a-stale",
                )
                for _ in range(10)
            ]
        )
        db.add(
            Event(
                business_id=tenant_a.id,
                event_type=EventType.LEAD_CREATED,
                entity_type="lead",
                entity_id=uuid4(),
                status=EventStatus.CLAIMED,
                locked_at=future_time,
                claimed_by="tenant-a-fresh",
            )
        )
        tenant_a_retry_run = WorkflowRun(
            business_id=tenant_a.id,
            status=WorkflowRunStatus.RUNNING,
            definition_snapshot={},
            results={},
            updated_at=future_time,
        )
        db.add(tenant_a_retry_run)
        db.flush()
        db.add(
            WorkflowAction(
                run_id=tenant_a_retry_run.id,
                action_type="webhook",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.RETRY_SCHEDULED,
                next_retry_at=future_time,
                enabled=True,
            )
        )

        # Tenant B: stale running runs only.
        db.add_all(
            [
                WorkflowRun(
                    business_id=tenant_b.id,
                    status=WorkflowRunStatus.RUNNING,
                    definition_snapshot={},
                    results={},
                    updated_at=stale_time,
                )
                for _ in range(5)
            ]
        )
        db.add(
            WorkflowRun(
                business_id=tenant_b.id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
                updated_at=future_time,
            )
        )

        # Tenant C: due retries only (plus one not-due retry).
        tenant_c_due_runs: list[WorkflowRun] = []
        for _ in range(8):
            run = WorkflowRun(
                business_id=tenant_c.id,
                status=WorkflowRunStatus.RUNNING,
                definition_snapshot={},
                results={},
                updated_at=future_time,
            )
            db.add(run)
            tenant_c_due_runs.append(run)
        tenant_c_not_due_run = WorkflowRun(
            business_id=tenant_c.id,
            status=WorkflowRunStatus.RUNNING,
            definition_snapshot={},
            results={},
            updated_at=future_time,
        )
        db.add(tenant_c_not_due_run)
        db.flush()
        db.add_all(
            [
                WorkflowAction(
                    run_id=run.id,
                    action_type="webhook",
                    parameters={},
                    execution_order=0,
                    status=WorkflowActionStatus.RETRY_SCHEDULED,
                    next_retry_at=stale_time,
                    enabled=True,
                )
                for run in tenant_c_due_runs
            ]
        )
        db.add(
            WorkflowAction(
                run_id=tenant_c_not_due_run.id,
                action_type="webhook",
                parameters={},
                execution_order=0,
                status=WorkflowActionStatus.RETRY_SCHEDULED,
                next_retry_at=future_time,
                enabled=True,
            )
        )
        db.commit()

        event_released = EventRecoveryService(db).release_stale_claims_global(stale_after_minutes=0)
        runs_released = WorkflowRunRecoveryService(db).release_stale_runs_global(stale_after_minutes=0)
        actions_requeued = WorkflowActionRecoveryService(db).requeue_due_retries_global()
        db.commit()

        assert event_released == 10
        assert runs_released == 5
        assert actions_requeued == 8

        tenant_a_pending_events = (
            db.query(Event)
            .filter(
                Event.business_id == tenant_a.id,
                Event.status == EventStatus.PENDING,
            )
            .count()
        )
        tenant_a_claimed_events = (
            db.query(Event)
            .filter(
                Event.business_id == tenant_a.id,
                Event.status == EventStatus.CLAIMED,
            )
            .count()
        )
        assert tenant_a_pending_events == 10
        assert tenant_a_claimed_events == 1

        tenant_b_failed_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant_b.id,
                WorkflowRun.status == WorkflowRunStatus.FAILED,
            )
            .count()
        )
        tenant_b_running_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant_b.id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )
        assert tenant_b_failed_runs == 5
        assert tenant_b_running_runs == 1

        tenant_c_pending_actions = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant_c.id,
                WorkflowAction.status == WorkflowActionStatus.PENDING,
            )
            .count()
        )
        tenant_c_retry_scheduled_actions = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant_c.id,
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
            )
            .count()
        )
        tenant_c_queued_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant_c.id,
                WorkflowRun.status == WorkflowRunStatus.QUEUED,
            )
            .count()
        )
        tenant_c_running_runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == tenant_c.id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .count()
        )
        assert tenant_c_pending_actions == 8
        assert tenant_c_retry_scheduled_actions == 1
        assert tenant_c_queued_runs == 8
        assert tenant_c_running_runs == 1

        # Cross-tenant safety checks for unrelated data.
        tenant_a_retry_scheduled_actions = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant_a.id,
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
            )
            .count()
        )
        assert tenant_a_retry_scheduled_actions == 1
