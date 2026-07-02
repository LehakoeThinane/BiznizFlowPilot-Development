"""Event dispatch worker flow and Celery tasks."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventStatus
from app.core.database import SessionLocal
from app.repositories.workflow import WorkflowActionRepository
from app.services.event import EventService
from app.workflow_engine import WorkflowDispatcher, WorkflowExecutor
from app.workflow_engine.definition_provider import DatabaseDefinitionProvider, DefinitionProvider
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


def process_next_event_for_business(
    db: Session,
    business_id: UUID,
    worker_id: str,
    provider: DefinitionProvider | None = None,
) -> dict[str, object]:
    """Claim one event, dispatch matching definitions, and commit the outcome."""
    event_service = EventService(db)

    event = event_service.claim_next_event(business_id=business_id, worker_id=worker_id)
    if event is None:
        return {
            "claimed": False,
            "runs_created": 0,
            "event_id": None,
            "event_status": None,
        }

    resolved_provider = provider or DatabaseDefinitionProvider(db)
    dispatcher = WorkflowDispatcher(db=db, definition_provider=resolved_provider)

    try:
        runs = dispatcher.dispatch(event)
        event.status = EventStatus.DISPATCHED
        event.locked_at = None
        event.claimed_by = None
        db.commit()

        return {
            "claimed": True,
            "runs_created": len(runs),
            "event_id": str(event.id),
            "event_status": event.status.value,
        }
    except Exception:
        db.rollback()
        db.refresh(event)
        event.status = EventStatus.FAILED
        event.locked_at = None
        event.claimed_by = None
        db.commit()

        raise


def execute_available_runs_for_business(
    db: Session,
    business_id: UUID,
    *,
    max_runs: int = 25,
) -> dict[str, object]:
    """Execute queued runs for one business until the queue is drained or max_runs is hit."""
    safe_max_runs = max(1, max_runs)
    executor = WorkflowExecutor(db)

    processed_runs = 0
    processed_run_ids: list[str] = []
    last_run_status: str | None = None

    for _ in range(safe_max_runs):
        result = executor.execute_next_run(business_id)
        if not result.get("claimed"):
            break

        processed_runs += 1
        run_id = result.get("run_id")
        if isinstance(run_id, str):
            processed_run_ids.append(run_id)
        run_status = result.get("run_status")
        last_run_status = run_status if isinstance(run_status, str) else last_run_status
        db.commit()

    return {
        "business_id": str(business_id),
        "processed_runs": processed_runs,
        "run_ids": processed_run_ids,
        "max_runs": safe_max_runs,
        "queue_drained": processed_runs < safe_max_runs,
        "last_run_status": last_run_status,
    }


@celery_app.task(bind=True, name="workflows.dispatch_next_event")
def dispatch_next_event_task(self, business_id: str, worker_id: str | None = None) -> dict[str, object]:
    """Celery task wrapper for event dispatch loop."""
    business_uuid = UUID(business_id)
    resolved_worker_id = worker_id or self.request.id or "celery-worker"

    with SessionLocal() as db:
        result = process_next_event_for_business(
            db=db,
            business_id=business_uuid,
            worker_id=resolved_worker_id,
        )
    if result.get("runs_created", 0):
        execute_available_runs_task.delay(business_id)
    return result


@celery_app.task(bind=True, name="workflows.execute_available_runs")
def execute_available_runs_task(
    self,
    business_id: str,
    max_runs: int = 25,
) -> dict[str, object]:
    """Celery task wrapper to execute queued runs for one tenant."""
    _ = self
    business_uuid = UUID(business_id)
    with SessionLocal() as db:
        return execute_available_runs_for_business(
            db=db,
            business_id=business_uuid,
            max_runs=max_runs,
        )


@celery_app.task(name="workflows.release_stale_claims")
def release_stale_claims_task(business_id: str, stale_after_minutes: int = 10) -> dict[str, int | str]:
    """Periodic recovery task to requeue stale claimed events."""
    business_uuid = UUID(business_id)

    with SessionLocal() as db:
        service = EventService(db)
        released = service.release_stale_claims(
            business_id=business_uuid,
            stale_after_minutes=stale_after_minutes,
        )
        db.commit()

    logger.warning(
        "Released %d stale event claims older than %d minutes for business %s",
        released,
        stale_after_minutes,
        business_id,
    )

    return {
        "business_id": business_id,
        "released": released,
    }


@celery_app.task(name="workflows.requeue_due_action_retries")
def requeue_due_action_retries_task(business_id: str) -> dict[str, int | str]:
    """Periodic task to move due retry-scheduled actions back to pending."""
    business_uuid = UUID(business_id)

    with SessionLocal() as db:
        action_repo = WorkflowActionRepository(db)
        requeued = action_repo.requeue_due_retries_for_business(
            db=db,
            business_id=business_uuid,
        )
        db.commit()

    logger.info(
        "Requeued %d due workflow actions for business %s",
        requeued,
        business_id,
    )
    return {
        "business_id": business_id,
        "requeued": requeued,
    }
