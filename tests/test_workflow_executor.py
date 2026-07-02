"""Tests for WorkflowExecutor dispatch path (Phase 5 step 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType, EventType, WorkflowActionStatus, WorkflowRunStatus
from app.models import WorkflowAction, WorkflowDefinition, WorkflowRun
from app.services.event import EventService
from app.workflow_engine import InMemoryDefinitionProvider, WorkflowDispatcher, WorkflowExecutor
from app.workflow_engine.action_config import ActionResult, BaseActionConfig
from app.workflow_engine.action_handlers import ActionHandler, ActionHandlerRegistry
from app.workflow_engine.email_provider import EmailProvider, EmailSendResult
from app.workflow_engine.handlers.send_email import SendEmailHandler
from app.workers import recovery as recovery_tasks


class _RetryableLogFailureHandler(ActionHandler):
    action_type = "log"

    def execute(self, *, db, action_config: BaseActionConfig, context):
        _ = db, action_config, context
        return ActionResult(
            status="failure",
            message="temporary downstream failure",
            data={"reason": "transient"},
            failure_type=ActionFailureType.RETRYABLE,
        )


class _ProgrammableLogHandler(ActionHandler):
    action_type = "log"

    def execute(self, *, db, action_config: BaseActionConfig, context):
        _ = db, context
        message = action_config.model_dump().get("message", "")
        if message.startswith("terminal"):
            return ActionResult(
                status="failure",
                message="terminal failure",
                data={},
                failure_type=ActionFailureType.TERMINAL,
            )
        if message.startswith("skippable"):
            return ActionResult(
                status="failure",
                message="skippable failure",
                data={},
                failure_type=ActionFailureType.SKIPPABLE,
            )
        return ActionResult(
            status="success",
            message=str(message),
            data={"ok": True},
            failure_type=None,
        )


class _FixedSessionContext:
    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type, exc, tb
        return False


class _FakeEmailProvider(EmailProvider):
    name = "fake-email"

    def __init__(self):
        self.send_count = 0

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        from_email: str | None = None,
        from_name: str | None = None,
        metadata: dict | None = None,
        timeout_seconds: int | None = None,
    ) -> EmailSendResult:
        _ = body, from_email, from_name, metadata, timeout_seconds
        self.send_count += 1
        return EmailSendResult(
            provider=self.name,
            recipient=recipient,
            subject=subject,
            message_id=f"msg-{self.send_count}",
            metadata={"accepted": True},
        )


class TestWorkflowExecutorDispatch:
    """Executor tests for run claiming and dispatch behavior."""

    def test_execute_next_run_returns_empty_when_none_queued(self, test_db: Session, owner_user):
        executor = WorkflowExecutor(test_db)

        result = executor.execute_next_run(owner_user.business_id)

        assert result["claimed"] is False
        assert result["run_id"] is None
        assert result["run_status"] is None
        assert result["executed_action_count"] == 0
        assert result["executed_action_ids"] == []
        assert result["retry_scheduled_count"] == 0
        assert result["retry_scheduled_action_ids"] == []
        assert result["failed_action_count"] == 0
        assert result["failed_action_ids"] == []
        assert result["skipped_action_count"] == 0
        assert result["skipped_action_ids"] == []

    def test_execute_next_run_dispatches_log_actions_successfully(self, test_db: Session, owner_user):
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
            name="Executor Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "first",
                    },
                    {
                        "action_type": "log",
                        "message": "second",
                        "enabled": False,
                    },
                    {
                        "action_type": "log",
                        "message": "third",
                    },
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
        run = runs[0]
        assert run.status == WorkflowRunStatus.QUEUED

        executor = WorkflowExecutor(test_db)
        result = executor.execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        assert result["claimed"] is True
        assert result["run_id"] == str(run.id)
        assert result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED

        all_actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )
        enabled_actions = [
            action
            for action in all_actions
            if action.enabled
        ]
        disabled_actions = [action for action in all_actions if not action.enabled]

        assert result["executed_action_count"] == len(enabled_actions) == 2
        assert result["executed_action_ids"] == [str(action.id) for action in enabled_actions]
        assert all(action.status == WorkflowActionStatus.COMPLETED for action in enabled_actions)
        assert all(action.result.get("status") == "success" for action in enabled_actions)
        assert all(action.executed_at is not None for action in enabled_actions)
        assert all("entity_type" in action.result.get("data", {}).get("context_keys", []) for action in enabled_actions)
        assert all("entity_id" in action.result.get("data", {}).get("context_keys", []) for action in enabled_actions)
        assert result["retry_scheduled_count"] == 0
        assert result["retry_scheduled_action_ids"] == []
        assert result["failed_action_count"] == 0
        assert result["failed_action_ids"] == []
        assert result["skipped_action_count"] == 0
        assert result["skipped_action_ids"] == []

        # Disabled actions are excluded from the execution loop.
        assert len(disabled_actions) == 1
        assert disabled_actions[0].status == WorkflowActionStatus.PENDING
        assert disabled_actions[0].result == {}

    def test_execute_next_run_schedules_retry_for_retryable_failure(self, test_db: Session, owner_user):
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
            name="Retry Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "retry me",
                        "retry_policy": {
                            "max_attempts": 2,
                            "initial_delay_seconds": 15,
                            "backoff_multiplier": 2.0,
                            "max_delay_seconds": 600,
                        },
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
        run = runs[0]

        registry = ActionHandlerRegistry()
        registry.register(_RetryableLogFailureHandler())
        executor = WorkflowExecutor(test_db, handler_registry=registry)

        before_execute = datetime.now(timezone.utc)
        result = executor.execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        action = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .first()
        )

        assert result["claimed"] is True
        assert result["run_status"] == WorkflowRunStatus.RUNNING.value
        assert result["executed_action_count"] == 0
        assert result["executed_action_ids"] == []
        assert result["retry_scheduled_count"] == 1
        assert result["retry_scheduled_action_ids"] == [str(action.id)]
        assert result["failed_action_count"] == 0
        assert result["failed_action_ids"] == []
        assert result["skipped_action_count"] == 0
        assert result["skipped_action_ids"] == []

        assert refreshed_run.status == WorkflowRunStatus.RUNNING
        assert action.status == WorkflowActionStatus.RETRY_SCHEDULED
        assert action.attempt_count == 1
        assert action.failure_type == ActionFailureType.RETRYABLE
        assert action.error == "temporary downstream failure"
        assert action.next_retry_at is not None
        next_retry_at = action.next_retry_at
        if next_retry_at.tzinfo is None:
            next_retry_at = next_retry_at.replace(tzinfo=timezone.utc)
        assert next_retry_at > before_execute

    def test_execute_next_run_does_not_inline_requeue_due_retries(self, test_db: Session, owner_user):
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
            name="Due Retry Definition",
            config={"actions": [{"action_type": "log", "message": "retryable"}]},
        )
        test_db.add(definition)
        test_db.commit()

        run = WorkflowDispatcher(
            db=test_db,
            definition_provider=InMemoryDefinitionProvider([definition]),
        ).dispatch(event)[0]
        test_db.commit()

        action = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .first()
        )
        action.status = WorkflowActionStatus.RETRY_SCHEDULED
        action.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        test_db.commit()

        result = WorkflowExecutor(test_db).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_action = test_db.query(WorkflowAction).filter(WorkflowAction.id == action.id).first()
        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()

        assert result["run_status"] == WorkflowRunStatus.RUNNING.value
        assert result["executed_action_count"] == 0
        assert result["retry_scheduled_count"] == 0
        assert refreshed_run.status == WorkflowRunStatus.RUNNING
        assert refreshed_action.status == WorkflowActionStatus.RETRY_SCHEDULED

    def test_webhook_retry_chain_requeue_then_success(
        self,
        test_db: Session,
        owner_user,
        monkeypatch,
    ):
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
            name="Webhook Retry Chain",
            config={
                "actions": [
                    {
                        "action_type": "webhook",
                        "url": "https://example.test/hooks",
                        "method": "POST",
                        "payload_template": {"kind": "test"},
                        "retry_policy": {
                            "max_attempts": 2,
                            "initial_delay_seconds": 1,
                            "backoff_multiplier": 1.0,
                            "max_delay_seconds": 60,
                        },
                    }
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        run = WorkflowDispatcher(
            db=test_db,
            definition_provider=InMemoryDefinitionProvider([definition]),
        ).dispatch(event)[0]
        test_db.commit()

        request_counter = {"count": 0}

        class _FakeResponse:
            def __init__(self, status_code: int, text: str = ""):
                self.status_code = status_code
                self.text = text

        def _fake_request(*, method, url, headers=None, json=None, timeout=None):
            _ = method, url, headers, json, timeout
            request_counter["count"] += 1
            if request_counter["count"] == 1:
                raise httpx.ReadTimeout("timeout")
            return _FakeResponse(status_code=200, text="ok")

        monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.httpx.request", _fake_request)

        first_result = WorkflowExecutor(test_db).execute_next_run(owner_user.business_id)
        test_db.commit()

        action = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .first()
        )
        assert first_result["run_status"] == WorkflowRunStatus.RUNNING.value
        assert first_result["retry_scheduled_count"] == 1
        assert action.status == WorkflowActionStatus.RETRY_SCHEDULED
        assert action.failure_type == ActionFailureType.RETRYABLE
        assert action.attempt_count == 1

        action.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        test_db.commit()

        monkeypatch.setattr(
            recovery_tasks,
            "SessionLocal",
            lambda: _FixedSessionContext(test_db),
        )
        requeue_result = recovery_tasks.requeue_due_action_retries_task.run()
        assert requeue_result == {"status": "ok", "rows_affected": 1}

        second_result = WorkflowExecutor(test_db).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        refreshed_action = test_db.query(WorkflowAction).filter(WorkflowAction.id == action.id).first()

        assert second_result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert second_result["executed_action_count"] == 1
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED
        assert refreshed_action.status == WorkflowActionStatus.COMPLETED
        assert refreshed_action.attempt_count == 1
        assert request_counter["count"] == 2

    def test_execute_next_run_marks_run_failed_on_terminal_failure(self, test_db: Session, owner_user):
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
            name="Terminal Failure Definition",
            config={
                "actions": [
                    {"action_type": "log", "message": "terminal-1"},
                    {"action_type": "log", "message": "ok-after-terminal"},
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        run = WorkflowDispatcher(db=test_db, definition_provider=provider).dispatch(event)[0]
        test_db.commit()

        registry = ActionHandlerRegistry()
        registry.register(_ProgrammableLogHandler())
        result = WorkflowExecutor(test_db, handler_registry=registry).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )

        assert result["run_status"] == WorkflowRunStatus.FAILED.value
        assert refreshed_run.status == WorkflowRunStatus.FAILED
        assert refreshed_run.error_message == "terminal failure"
        assert result["failed_action_count"] == 1
        assert result["skipped_action_count"] == 0
        assert result["executed_action_count"] == 0
        assert actions[0].status == WorkflowActionStatus.FAILED
        assert actions[1].status == WorkflowActionStatus.PENDING

    def test_execute_next_run_continue_on_failure_completes_run(self, test_db: Session, owner_user):
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
            name="Continue On Failure Definition",
            config={
                "actions": [
                    {
                        "action_type": "log",
                        "message": "terminal-continue",
                        "continue_on_failure": True,
                    },
                    {"action_type": "log", "message": "ok-after-failure"},
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        run = WorkflowDispatcher(db=test_db, definition_provider=provider).dispatch(event)[0]
        test_db.commit()

        registry = ActionHandlerRegistry()
        registry.register(_ProgrammableLogHandler())
        result = WorkflowExecutor(test_db, handler_registry=registry).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )

        assert result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED
        assert result["failed_action_count"] == 1
        assert result["executed_action_count"] == 1
        assert result["skipped_action_count"] == 0
        assert actions[0].status == WorkflowActionStatus.FAILED
        assert actions[1].status == WorkflowActionStatus.COMPLETED

    def test_execute_next_run_skippable_failure_keeps_run_completable(self, test_db: Session, owner_user):
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
            name="Skippable Definition",
            config={
                "actions": [
                    {"action_type": "log", "message": "skippable-1"},
                    {"action_type": "log", "message": "ok-after-skip"},
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        run = WorkflowDispatcher(db=test_db, definition_provider=provider).dispatch(event)[0]
        test_db.commit()

        registry = ActionHandlerRegistry()
        registry.register(_ProgrammableLogHandler())
        result = WorkflowExecutor(test_db, handler_registry=registry).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )

        assert result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED
        assert result["skipped_action_count"] == 1
        assert result["failed_action_count"] == 0
        assert result["executed_action_count"] == 1
        assert actions[0].status == WorkflowActionStatus.SKIPPED
        assert actions[1].status == WorkflowActionStatus.COMPLETED

    def test_execute_next_run_dispatches_send_email_action(self, test_db: Session, owner_user, sample_lead):
        event_service = EventService(test_db)
        event = event_service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=sample_lead.id,
            actor_id=owner_user.user_id,
        )

        definition = WorkflowDefinition(
            id=uuid4(),
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            is_active=True,
            name="Send Email Definition",
            config={
                "actions": [
                    {
                        "action_type": "send_email",
                        "recipient": "{customer.email}",
                        "subject": "Welcome {lead.name}",
                        "body_template": "Hi {lead.name}",
                    }
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        run = WorkflowDispatcher(
            db=test_db,
            definition_provider=InMemoryDefinitionProvider([definition]),
        ).dispatch(event)[0]
        test_db.commit()

        provider = _FakeEmailProvider()
        registry = ActionHandlerRegistry()
        registry.register(SendEmailHandler(provider=provider))
        result = WorkflowExecutor(test_db, handler_registry=registry).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        action = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .first()
        )

        assert result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED
        assert action.status == WorkflowActionStatus.COMPLETED
        assert action.result["status"] == "success"
        assert action.result["data"]["provider"] == "fake-email"
        assert provider.send_count == 1

    def test_integration_dispatch_materialize_execute_mixed_outcomes(self, test_db: Session, owner_user):
        """End-to-end: dispatch -> action materialization -> execute with skippable + success."""
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
            name="Mixed Outcome Integration Definition",
            config={
                "actions": [
                    {"action_type": "log", "message": "ok-first"},
                    {"action_type": "log", "message": "skippable-middle"},
                    {"action_type": "log", "message": "ok-last"},
                ]
            },
        )
        test_db.add(definition)
        test_db.commit()

        provider = InMemoryDefinitionProvider([definition])
        run = WorkflowDispatcher(db=test_db, definition_provider=provider).dispatch(event)[0]
        test_db.commit()

        materialized_actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )
        assert len(materialized_actions) == 3
        assert [action.status for action in materialized_actions] == [WorkflowActionStatus.PENDING] * 3

        registry = ActionHandlerRegistry()
        registry.register(_ProgrammableLogHandler())
        result = WorkflowExecutor(test_db, handler_registry=registry).execute_next_run(owner_user.business_id)
        test_db.commit()

        refreshed_run = test_db.query(WorkflowRun).filter(WorkflowRun.id == run.id).first()
        executed_actions = (
            test_db.query(WorkflowAction)
            .filter(WorkflowAction.run_id == run.id)
            .order_by(WorkflowAction.execution_order.asc())
            .all()
        )

        assert result["run_status"] == WorkflowRunStatus.COMPLETED.value
        assert refreshed_run.status == WorkflowRunStatus.COMPLETED
        assert result["executed_action_count"] == 2
        assert result["skipped_action_count"] == 1
        assert result["failed_action_count"] == 0
        assert [action.status for action in executed_actions] == [
            WorkflowActionStatus.COMPLETED,
            WorkflowActionStatus.SKIPPED,
            WorkflowActionStatus.COMPLETED,
        ]
