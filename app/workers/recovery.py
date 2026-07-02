"""Celery recovery tasks for operational maintenance loops."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.recovery import (
    EventRecoveryService,
    WorkflowActionRecoveryService,
    WorkflowRunRecoveryService,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_recovery_job(
    *,
    job_name: str,
    operation: Callable[[Session], int],
    log_params: dict[str, object],
) -> dict[str, int | str]:
    """Run one recovery operation with consistent session and logging behavior."""
    started_at = perf_counter()
    with SessionLocal() as db:
        try:
            rows_affected = operation(db)
            db.commit()
        except Exception:
            db.rollback()
            duration_ms = int((perf_counter() - started_at) * 1000)
            logger.exception(
                "%s failed duration_ms=%d params=%s",
                job_name,
                duration_ms,
                log_params,
            )
            raise

    duration_ms = int((perf_counter() - started_at) * 1000)
    logger.info(
        "%s completed rows_affected=%d duration_ms=%d params=%s",
        job_name,
        rows_affected,
        duration_ms,
        log_params,
    )
    return {
        "status": "ok",
        "rows_affected": int(rows_affected),
    }


@celery_app.task(name="ops.release_stale_event_claims")
def release_stale_event_claims_task(stale_after_minutes: int = 10) -> dict[str, int | str]:
    """Release stale event claims across all tenants."""
    return _run_recovery_job(
        job_name="ops.release_stale_event_claims",
        operation=lambda db: EventRecoveryService(db).release_stale_claims_global(
            stale_after_minutes=stale_after_minutes
        ),
        log_params={"stale_after_minutes": stale_after_minutes},
    )


@celery_app.task(name="ops.requeue_due_action_retries")
def requeue_due_action_retries_task() -> dict[str, int | str]:
    """Requeue due action retries across all tenants."""
    return _run_recovery_job(
        job_name="ops.requeue_due_action_retries",
        operation=lambda db: WorkflowActionRecoveryService(db).requeue_due_retries_global(),
        log_params={},
    )


@celery_app.task(name="ops.release_stale_workflow_runs")
def release_stale_workflow_runs_task(stale_after_minutes: int = 30) -> dict[str, int | str]:
    """Mark stale running workflow runs as failed across all tenants."""
    return _run_recovery_job(
        job_name="ops.release_stale_workflow_runs",
        operation=lambda db: WorkflowRunRecoveryService(db).release_stale_runs_global(
            stale_after_minutes=stale_after_minutes
        ),
        log_params={"stale_after_minutes": stale_after_minutes},
    )
