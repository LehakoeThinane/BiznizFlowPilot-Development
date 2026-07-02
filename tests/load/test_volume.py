"""Volume-oriented load tests for mixed outcome and slow-handler behavior."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from app.core.enums import EventType, WorkflowActionStatus, WorkflowRunStatus
from app.models import WorkflowAction, WorkflowRun
from app.services.recovery import WorkflowActionRecoveryService

from .handlers import build_test_handler_registry
from .utils import create_business, dispatch_events, run_worker_pool, seed_definitions, seed_events


class TestWorkflowVolumeLoad:
    def test_completion_failure_timeout_distribution(self, load_db):
        """Check 1: validate mixed outcome distribution under volume."""
        db, created_business_ids = load_db
        tenant = create_business(db, label="load-volume")
        created_business_ids.append(tenant.id)

        seed_definitions(
            db=db,
            business_id=tenant.id,
            count=1,
            event_type=EventType.LEAD_CREATED,
            actions=[{"action_type": "log", "message": "success-path"}],
        )
        seed_definitions(
            db=db,
            business_id=tenant.id,
            count=1,
            event_type=EventType.TASK_CREATED,
            actions=[{"action_type": "create_task", "title": "terminal-path"}],
        )
        seed_definitions(
            db=db,
            business_id=tenant.id,
            count=1,
            event_type=EventType.TASK_ASSIGNED,
            actions=[
                {
                    "action_type": "webhook",
                    "url": "https://example.test/retry",
                    "method": "POST",
                    "payload_template": {"kind": "retry"},
                    "retry_policy": {
                        "max_attempts": 2,
                        "initial_delay_seconds": 1,
                        "backoff_multiplier": 1.0,
                        "max_delay_seconds": 60,
                    },
                }
            ],
        )
        db.commit()

        success_events = seed_events(db, tenant.id, 80, EventType.LEAD_CREATED)
        terminal_events = seed_events(db, tenant.id, 15, EventType.TASK_CREATED)
        retryable_events = seed_events(db, tenant.id, 5, EventType.TASK_ASSIGNED)
        dispatch_events(db, [*success_events, *terminal_events, *retryable_events])

        registry = build_test_handler_registry()
        first_pass = run_worker_pool(
            business_ids=[tenant.id],
            worker_count=3,
            max_iterations=300,
            timeout_seconds=90,
            handler_registry=registry,
        )
        assert first_pass["errors"] == []
        assert first_pass["timed_out_workers"] == 0

        # Exhaust retries: first pass schedules retries, two requeue+execute
        # cycles drive max_attempts=2 to terminal run failure.
        recovery = WorkflowActionRecoveryService(db)
        for _ in range(2):
            run_ids = [
                run_id
                for (run_id,) in (
                    db.query(WorkflowRun.id)
                    .filter(WorkflowRun.business_id == tenant.id)
                    .all()
                )
            ]
            (
                db.query(WorkflowAction)
                .filter(
                    WorkflowAction.run_id.in_(run_ids),
                    WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
                    WorkflowAction.next_retry_at.is_not(None),
                )
                .update(
                    {WorkflowAction.next_retry_at: datetime.now(timezone.utc) - timedelta(seconds=1)},
                    synchronize_session=False,
                )
            )
            db.commit()

            requeued = recovery.requeue_due_retries_global()
            db.commit()
            assert requeued == 5

            pass_result = run_worker_pool(
                business_ids=[tenant.id],
                worker_count=3,
                max_iterations=300,
                timeout_seconds=90,
                handler_registry=registry,
            )
            assert pass_result["errors"] == []
            assert pass_result["timed_out_workers"] == 0

        runs = db.query(WorkflowRun).filter(WorkflowRun.business_id == tenant.id).all()
        assert len(runs) == 100

        completed = [run for run in runs if run.status == WorkflowRunStatus.COMPLETED]
        failed = [run for run in runs if run.status == WorkflowRunStatus.FAILED]
        running = [run for run in runs if run.status == WorkflowRunStatus.RUNNING]
        queued = [run for run in runs if run.status == WorkflowRunStatus.QUEUED]

        assert len(completed) == 80
        assert len(failed) == 20  # 15 terminal + 5 retry-exhausted
        assert len(running) == 0
        assert len(queued) == 0

        pending_retries = (
            db.query(WorkflowAction)
            .join(WorkflowRun, WorkflowAction.run_id == WorkflowRun.id)
            .filter(
                WorkflowRun.business_id == tenant.id,
                WorkflowAction.status == WorkflowActionStatus.RETRY_SCHEDULED,
            )
            .count()
        )
        assert pending_retries == 0

    def test_slow_handler_timeout_enforcement(self, load_db):
        """Check 6: slow handlers honor timeout and do not hang worker pool."""
        db, created_business_ids = load_db
        tenant = create_business(db, label="load-slow")
        created_business_ids.append(tenant.id)

        seed_definitions(
            db=db,
            business_id=tenant.id,
            count=1,
            event_type=EventType.LEAD_CREATED,
            actions=[
                {
                    "action_type": "send_email",
                    "recipient": "load-test@example.test",
                    "subject": "slow-handler-timeout",
                    # SlowHandler reads sleep_seconds from body_template.
                    "body_template": "10",
                    "timeout_seconds": 3,
                }
            ],
        )
        db.commit()

        events = seed_events(db, tenant.id, 10, EventType.LEAD_CREATED)
        dispatch_events(db, events)

        start = time.monotonic()
        result = run_worker_pool(
            business_ids=[tenant.id],
            worker_count=2,
            max_iterations=100,
            timeout_seconds=60,
            handler_registry=build_test_handler_registry(),
        )
        elapsed = time.monotonic() - start

        assert result["errors"] == []
        assert result["timed_out_workers"] == 0

        runs = db.query(WorkflowRun).filter(WorkflowRun.business_id == tenant.id).all()
        assert len(runs) == 10
        assert all(run.status == WorkflowRunStatus.FAILED for run in runs)
        assert all("timeout" in (run.error_message or "").lower() for run in runs)

        # Timeout-enforced behavior should complete much faster than full 10s sleeps.
        assert elapsed < 45, f"Slow handler timeout behavior regressed: elapsed={elapsed:.2f}s"
