"""Celery application wiring."""

from datetime import timedelta

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "biznizflowpilot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "release-stale-event-claims": {
            "task": "ops.release_stale_event_claims",
            "schedule": timedelta(seconds=settings.stale_claim_check_interval_seconds),
            "args": (10,),
        },
        "requeue-due-action-retries": {
            "task": "ops.requeue_due_action_retries",
            "schedule": timedelta(seconds=settings.action_retry_check_interval_seconds),
        },
        "release-stale-workflow-runs": {
            "task": "ops.release_stale_workflow_runs",
            "schedule": timedelta(seconds=settings.stale_run_check_interval_seconds),
            "args": (30,),
        },
        "process-followups": {
            "task": "ops.process_followups",
            "schedule": timedelta(seconds=settings.followup_check_interval_seconds),
            "args": (24,),
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
