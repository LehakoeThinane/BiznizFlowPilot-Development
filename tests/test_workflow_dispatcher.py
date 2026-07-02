"""Tests for Phase 4 workflow dispatch architecture."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.enums import EventStatus, EventType, WorkflowRunStatus
from app.models import WorkflowAction, WorkflowDefinition, WorkflowRun
from app.repositories.event import EventRepository
from app.services.event import EventService
from app.workflow_engine import DatabaseDefinitionProvider, InMemoryDefinitionProvider, WorkflowDispatcher
from app.workers import event_dispatch
from app.workers.event_dispatch import execute_available_runs_for_business, process_next_event_for_business


class _FixedSessionContext:
    """Context manager wrapper that returns a provided SQLAlchemy session."""

    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False


class TestWorkflowDispatcher:
    """Unit tests for dispatcher behavior."""

    def test_dispatch_no_matches(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
        )
        test_db.commit()

        provider = InMemoryDefinitionProvider([])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)

        assert runs == []

    def test_dispatch_single_match_creates_run(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
        )

        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Lead Created Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "Lead created",
                    }
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)
        test_db.commit()

        assert len(runs) == 1
        assert runs[0].event_id == event.id
        assert runs[0].workflow_definition_id == definition.id
        assert runs[0].status == WorkflowRunStatus.QUEUED
        assert runs[0].definition_snapshot["event_type"] == EventType.LEAD_CREATED.value
        run_actions = test_db.query(WorkflowAction).filter(WorkflowAction.run_id == runs[0].id).all()
        assert len(run_actions) == 1
        assert run_actions[0].action_type == "log"
        assert run_actions[0].execution_order == 0

    def test_dispatch_multiple_matches_creates_multiple_runs(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_CREATED,
            entity_type="task",
            entity_id=uuid4(),
        )

        definitions = [
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.TASK_CREATED,
                is_active=True,
                name="Definition 1",
                config={
                    "actions": [
                        {
                            "action_type": "log",
                            "message": "First action",
                        },
                        {
                            "action_type": "log",
                            "message": "Second action",
                        },
                    ]
                },
            ),
            WorkflowDefinition(
                id=uuid4(),
                business_id=owner_user.business_id,
                event_type=EventType.TASK_CREATED,
                is_active=True,
                name="Definition 2",
                config={
                    "actions": [
                        {
                            "action_type": "log",
                            "message": "Only action",
                        }
                    ]
                },
            ),
        ]
        test_db.add_all(definitions)
        test_db.commit()

        provider = InMemoryDefinitionProvider(definitions)
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)
        test_db.commit()

        assert len(runs) == 2
        assert {run.workflow_definition_id for run in runs} == {definition.id for definition in definitions}
        run_actions = test_db.query(WorkflowAction).filter(WorkflowAction.run_id.in_([run.id for run in runs])).all()
        assert len(run_actions) == 3

    def test_dispatch_skips_inactive_definitions(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            entity_type="lead",
            entity_id=uuid4(),
        )

        active = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            is_active=True,
            name="Active Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "Active only",
                    }
                ]
            },
        )
        inactive = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            is_active=False,
            name="Inactive Definition",
        )
        test_db.add_all([active, inactive])
        test_db.commit()

        provider = InMemoryDefinitionProvider([active, inactive])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)
        test_db.commit()

        assert len(runs) == 1
        assert runs[0].workflow_definition_id == active.id

    def test_dispatch_skips_malformed_definitions(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_ASSIGNED,
            entity_type="task",
            entity_id=uuid4(),
        )

        good_definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.TASK_ASSIGNED,
            is_active=True,
            name="Good Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "Good action",
                    }
                ]
            },
        )
        malformed_definition = SimpleNamespace(id=uuid4(), business_id=owner_user.business_id)

        test_db.add(good_definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([good_definition, malformed_definition])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)
        test_db.commit()

        assert len(runs) == 1
        assert runs[0].workflow_definition_id == good_definition.id

    def test_dispatch_duplicate_blocked_by_unique_index(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_COMPLETED,
            entity_type="task",
            entity_id=uuid4(),
        )

        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.TASK_COMPLETED,
            is_active=True,
            name="Completion Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "Run once",
                    }
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        first_runs = dispatcher.dispatch(event)
        test_db.commit()

        second_runs = dispatcher.dispatch(event)
        test_db.commit()

        persisted_runs = (
            test_db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == owner_user.business_id,
                WorkflowRun.event_id == event.id,
                WorkflowRun.workflow_definition_id == definition.id,
            )
            .all()
        )

        assert len(first_runs) == 1
        assert second_runs == []
        assert len(persisted_runs) == 1

    def test_dispatch_invalid_action_config_rolls_back_definition_savepoint(self, test_db: Session, owner_user):
        """Invalid action config should skip definition and create no run/actions for it."""
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
        )

        valid_definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Valid Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "valid",
                    }
                ]
            },
        )
        invalid_definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Invalid Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        # missing required `message`
                    }
                ]
            },
        )
        test_db.add_all([valid_definition, invalid_definition])
        test_db.commit()

        provider = InMemoryDefinitionProvider([valid_definition, invalid_definition])
        dispatcher = WorkflowDispatcher(db=test_db, definition_provider=provider)

        runs = dispatcher.dispatch(event)
        test_db.commit()

        assert len(runs) == 1
        assert runs[0].workflow_definition_id == valid_definition.id
        actions = test_db.query(WorkflowAction).filter(WorkflowAction.run_id == runs[0].id).all()
        assert len(actions) == 1
        assert actions[0].action_type == "log"

    def test_database_definition_provider_returns_active_event_matches(self, test_db: Session, owner_user):
        active = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Active Definition",
        )
        inactive = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=False,
            name="Inactive Definition",
        )
        soft_deleted = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Soft Deleted Definition",
            deleted_at=datetime.now(timezone.utc),
        )
        different_event = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.TASK_CREATED,
            is_active=True,
            name="Other Event Definition",
        )
        test_db.add_all([active, inactive, soft_deleted, different_event])
        test_db.commit()

        provider = DatabaseDefinitionProvider(test_db)
        definitions = provider.get_definitions_for_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
        )

        assert {definition.id for definition in definitions} == {active.id}


class TestWorkerDispatchLoop:
    """Integration tests for claim -> dispatch -> commit loop."""

    def test_claim_dispatch_commit_with_partial_failure(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
            actor_id=owner_user.user_id,
        )

        valid_definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Valid Definition",
        )
        malformed_definition = SimpleNamespace(id=uuid4(), business_id=owner_user.business_id)

        test_db.add(valid_definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([valid_definition, malformed_definition])
        result = process_next_event_for_business(
            db=test_db,
            business_id=owner_user.business_id,
            worker_id="worker-integration",
            provider=provider,
        )

        refreshed_event = EventRepository(test_db).get(owner_user.business_id, event.id)
        runs = (
            test_db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == owner_user.business_id,
                WorkflowRun.event_id == event.id,
            )
            .all()
        )

        assert result["claimed"] is True
        assert result["runs_created"] == 1
        assert result["event_status"] == EventStatus.DISPATCHED.value
        assert refreshed_event.status == EventStatus.DISPATCHED
        assert len(runs) == 1
        assert runs[0].workflow_definition_id == valid_definition.id
        assert runs[0].status == WorkflowRunStatus.QUEUED

    def test_claim_dispatch_defaults_to_database_provider(self, test_db: Session, owner_user):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
            actor_id=owner_user.user_id,
        )

        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="DB-backed Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "from-db-provider",
                    }
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        result = process_next_event_for_business(
            db=test_db,
            business_id=owner_user.business_id,
            worker_id="worker-integration",
            provider=None,
        )

        refreshed_event = EventRepository(test_db).get(owner_user.business_id, event.id)
        runs = (
            test_db.query(WorkflowRun)
            .filter(
                WorkflowRun.business_id == owner_user.business_id,
                WorkflowRun.event_id == event.id,
            )
            .all()
        )

        assert result["claimed"] is True
        assert result["runs_created"] == 1
        assert result["event_status"] == EventStatus.DISPATCHED.value
        assert refreshed_event.status == EventStatus.DISPATCHED
        assert len(runs) == 1
        assert runs[0].workflow_definition_id == definition.id


class TestDispatchExecutionBridge:
    """Tests for dispatch task -> execute task wiring."""

    def test_dispatch_task_enqueues_execution_when_runs_created(
        self,
        test_db: Session,
        owner_user,
        monkeypatch: pytest.MonkeyPatch,
    ):
        event_service = EventService(test_db)
        event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
            actor_id=owner_user.user_id,
        )
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Bridge Definition",
            config={"actions": [{"action_type": "log", "message": "run"}]},
        )
        test_db.add(definition)
        test_db.commit()

        monkeypatch.setattr(
            event_dispatch,
            "SessionLocal",
            lambda: _FixedSessionContext(test_db),
        )

        enqueue_calls: list[str] = []

        def _delay(business_id: str) -> None:
            enqueue_calls.append(business_id)

        monkeypatch.setattr(
            event_dispatch,
            "execute_available_runs_task",
            SimpleNamespace(delay=_delay),
        )

        result = event_dispatch.dispatch_next_event_task.run(
            business_id=str(owner_user.business_id),
            worker_id="dispatch-test-worker",
        )

        assert result["claimed"] is True
        assert result["runs_created"] == 1
        assert enqueue_calls == [str(owner_user.business_id)]

    def test_dispatch_task_skips_enqueue_when_no_runs_created(
        self,
        test_db: Session,
        owner_user,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            event_dispatch,
            "SessionLocal",
            lambda: _FixedSessionContext(test_db),
        )

        enqueue_calls: list[str] = []

        def _delay(business_id: str) -> None:
            enqueue_calls.append(business_id)

        monkeypatch.setattr(
            event_dispatch,
            "execute_available_runs_task",
            SimpleNamespace(delay=_delay),
        )

        result = event_dispatch.dispatch_next_event_task.run(
            business_id=str(owner_user.business_id),
            worker_id="dispatch-test-worker",
        )

        assert result["claimed"] is False
        assert result["runs_created"] == 0
        assert enqueue_calls == []

    def test_execute_available_runs_respects_max_runs(
        self,
        test_db: Session,
        owner_user,
    ):
        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Execute Loop Definition",
            config={"actions": [{"action_type": "log", "message": "ok"}]},
        )
        test_db.add(definition)
        test_db.commit()

        dispatcher = WorkflowDispatcher(
            db=test_db,
            definition_provider=InMemoryDefinitionProvider([definition]),
        )
        event_service = EventService(test_db)
        for _ in range(3):
            event = event_service.create_event(
                business_id=owner_user.business_id,
                event_type=EventType.LEAD_CREATED,
                entity_type="lead",
                entity_id=uuid4(),
                actor_id=owner_user.user_id,
            )
            dispatcher.dispatch(event)
            test_db.commit()

        summary = execute_available_runs_for_business(
            db=test_db,
            business_id=owner_user.business_id,
            max_runs=2,
        )

        runs = (
            test_db.query(WorkflowRun)
            .filter(WorkflowRun.business_id == owner_user.business_id)
            .all()
        )
        completed_count = sum(1 for run in runs if run.status == WorkflowRunStatus.COMPLETED)
        queued_count = sum(1 for run in runs if run.status == WorkflowRunStatus.QUEUED)

        assert summary["processed_runs"] == 2
        assert summary["max_runs"] == 2
        assert summary["queue_drained"] is False
        assert len(summary["run_ids"]) == 2
        assert summary["last_run_status"] == WorkflowRunStatus.COMPLETED.value
        assert completed_count == 2
        assert queued_count == 1
