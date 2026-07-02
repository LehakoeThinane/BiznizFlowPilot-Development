"""Load tests for core concurrency contracts."""

from __future__ import annotations

from sqlalchemy import func

from app.core.enums import EventType, WorkflowRunStatus
from app.models import WorkflowRun

from .utils import (
    create_business,
    dispatch_events,
    run_dispatch_race,
    run_worker_pool,
    seed_definitions,
    seed_events,
)


class TestWorkflowConcurrencyLoad:
    def test_duplicate_run_creation_is_blocked_under_concurrent_dispatch(self, load_db):
        """Check 2: one event + many definitions yields exactly one run per definition."""
        db, created_business_ids = load_db
        business = create_business(db, label="load-race")
        created_business_ids.append(business.id)

        definitions = seed_definitions(
            db=db,
            business_id=business.id,
            count=10,
            event_type=EventType.LEAD_CREATED,
            actions=[{"action_type": "log", "message": "race"}],
        )
        event = seed_events(
            db=db,
            business_id=business.id,
            count=1,
            event_type=EventType.LEAD_CREATED,
        )[0]
        db.commit()

        race_result = run_dispatch_race(
            business_id=business.id,
            event_id=event.id,
            worker_count=5,
            iterations_per_worker=3,
            timeout_seconds=30,
        )

        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == business.id,
                WorkflowRun.event_id == event.id,
            )
            .all()
        )
        per_definition = (
            db.query(
                WorkflowRun.workflow_definition_id,
                func.count(WorkflowRun.id),
            )
            .filter(
                WorkflowRun.business_id == business.id,
                WorkflowRun.event_id == event.id,
            )
            .group_by(WorkflowRun.workflow_definition_id)
            .all()
        )

        assert race_result["errors"] == []
        assert race_result["timed_out_workers"] == 0
        assert len(runs) == len(definitions) == 10
        assert len(per_definition) == 10
        assert all(count == 1 for _, count in per_definition)

    def test_multi_worker_claiming_processes_each_run_once(self, load_db):
        """Check 5: concurrent workers should process each queued run exactly once."""
        db, created_business_ids = load_db
        business = create_business(db, label="load-claim")
        created_business_ids.append(business.id)

        seed_definitions(
            db=db,
            business_id=business.id,
            count=1,
            event_type=EventType.LEAD_CREATED,
            actions=[{"action_type": "log", "message": "process"}],
        )
        events = seed_events(
            db=db,
            business_id=business.id,
            count=100,
            event_type=EventType.LEAD_CREATED,
        )
        created_runs = dispatch_events(db, events)
        db.commit()
        assert created_runs == 100

        pool_result = run_worker_pool(
            business_ids=[business.id],
            worker_count=5,
            max_iterations=300,
            timeout_seconds=45,
        )

        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.business_id == business.id)
            .all()
        )
        completed = [run for run in runs if run.status == WorkflowRunStatus.COMPLETED]
        queued_or_running = [
            run
            for run in runs
            if run.status in {WorkflowRunStatus.QUEUED, WorkflowRunStatus.RUNNING}
        ]

        claimed_run_ids = pool_result["claimed_run_ids"]
        assert pool_result["errors"] == []
        assert pool_result["timed_out_workers"] == 0
        assert len(runs) == 100
        assert len(completed) == 100
        assert queued_or_running == []
        assert len(claimed_run_ids) == 100
        assert len(set(claimed_run_ids)) == 100
        assert all(run.started_at is not None for run in runs)
        assert all(run.finished_at is not None for run in runs)

