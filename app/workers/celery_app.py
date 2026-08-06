"""Celery application wiring."""

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

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
        "send-trial-reminders": {
            "task": "ops.send_trial_reminders",
            "schedule": timedelta(seconds=settings.trial_reminder_check_interval_seconds),
        },
        "poll-linkedin-leads": {
            "task": "ops.poll_linkedin_leads",
            "schedule": timedelta(seconds=settings.linkedin_lead_poll_interval_seconds),
        },
        "daily-blog-autopublish": {
            "task": "ops.daily_blog_autopublish",
            # 04:00 UTC = 06:00 SAST - South Africa has no DST, fixed offset.
            "schedule": crontab(hour=4, minute=0),
        },
    },
)

celery_app.autodiscover_tasks(["app.workers"])
