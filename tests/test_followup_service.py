"""Tests for FollowUpService and FollowUpGlobalService."""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.lead import Lead
from app.models.task import Task
from app.models.event import Event
from app.core.enums import EventStatus, EventType
from app.services.followup import FollowUpService, FollowUpGlobalService


def _make_old_lead(db: Session, business_id, status="new", hours_old=48):
    """Create a lead whose updated_at is `hours_old` hours in the past."""
    lead = Lead(
        id=uuid4(),
        business_id=business_id,
        status=status,
    )
    db.add(lead)
    db.flush()
    # Manually backdate updated_at so the idle check picks it up
    stale_ts = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    db.execute(
        Lead.__table__.update()
        .where(Lead.id == lead.id)
        .values(updated_at=stale_ts)
    )
    db.flush()
    db.refresh(lead)
    return lead


# ── process_idle_leads ────────────────────────────────────────────────────────

class TestProcessIdleLeads:
    def test_no_leads_returns_zero(self, test_db: Session, owner_business: Business):
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_idle_lead_creates_followup_task(self, test_db: Session, owner_business: Business):
        _make_old_lead(test_db, owner_business.id, status="new", hours_old=48)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 1
        task = test_db.query(Task).filter(Task.business_id == owner_business.id).first()
        assert task is not None
        assert task.status == "pending"
        assert task.priority == "high"
        assert "follow" in task.title.lower()

    def test_contacted_lead_is_also_idle(self, test_db: Session, owner_business: Business):
        _make_old_lead(test_db, owner_business.id, status="contacted", hours_old=48)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 1

    def test_won_lead_is_skipped(self, test_db: Session, owner_business: Business):
        _make_old_lead(test_db, owner_business.id, status="won", hours_old=48)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_lost_lead_is_skipped(self, test_db: Session, owner_business: Business):
        _make_old_lead(test_db, owner_business.id, status="lost", hours_old=48)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_recently_updated_lead_is_skipped(self, test_db: Session, owner_business: Business):
        # Lead updated only 1 hour ago — not idle under 24h threshold
        _make_old_lead(test_db, owner_business.id, status="new", hours_old=1)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_recent_event_prevents_followup(self, test_db: Session, owner_business: Business):
        lead = _make_old_lead(test_db, owner_business.id, status="new", hours_old=48)
        # Add a recent event referencing this lead
        event = Event(
            id=uuid4(),
            business_id=owner_business.id,
            event_type=EventType.LEAD_UPDATED,
            entity_type="lead",
            entity_id=lead.id,
            description="Recent update",
            status=EventStatus.PENDING,
        )
        test_db.add(event)
        test_db.flush()
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_existing_followup_task_prevents_duplicate(self, test_db: Session, owner_business: Business):
        lead = _make_old_lead(test_db, owner_business.id, status="new", hours_old=48)
        existing = Task(
            id=uuid4(),
            business_id=owner_business.id,
            lead_id=lead.id,
            title="Follow up with customer",
            status="pending",
            priority="high",
        )
        test_db.add(existing)
        test_db.flush()
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_other_business_lead_not_affected(self, test_db: Session, owner_business: Business, other_business: Business):
        _make_old_lead(test_db, other_business.id, status="new", hours_old=48)
        service = FollowUpService(test_db)
        result = service.process_idle_leads(owner_business.id, idle_hours=24)
        assert result == 0

    def test_creates_event_alongside_task(self, test_db: Session, owner_business: Business):
        _make_old_lead(test_db, owner_business.id, status="new", hours_old=48)
        service = FollowUpService(test_db)
        service.process_idle_leads(owner_business.id, idle_hours=24)
        event = (
            test_db.query(Event)
            .filter(
                Event.business_id == owner_business.id,
                Event.event_type == EventType.TASK_CREATED,
            )
            .first()
        )
        assert event is not None
        assert event.data["trigger"] == "idle_lead_followup"


# ── mark_overdue_tasks ────────────────────────────────────────────────────────

class TestMarkOverdueTasks:
    def _make_overdue_task(self, db: Session, business_id, status="pending"):
        task = Task(
            id=uuid4(),
            business_id=business_id,
            title="Overdue task",
            status=status,
            priority="medium",
            due_date=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(task)
        db.flush()
        return task

    def test_no_tasks_returns_zero(self, test_db: Session, owner_business: Business):
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 0

    def test_overdue_pending_task_marked(self, test_db: Session, owner_business: Business):
        self._make_overdue_task(test_db, owner_business.id, status="pending")
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 1
        task = test_db.query(Task).filter(Task.business_id == owner_business.id).first()
        assert task.status == "overdue"

    def test_overdue_in_progress_task_marked(self, test_db: Session, owner_business: Business):
        self._make_overdue_task(test_db, owner_business.id, status="in_progress")
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 1

    def test_completed_task_not_marked_overdue(self, test_db: Session, owner_business: Business):
        self._make_overdue_task(test_db, owner_business.id, status="done")
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 0

    def test_future_due_date_not_marked(self, test_db: Session, owner_business: Business):
        task = Task(
            id=uuid4(),
            business_id=owner_business.id,
            title="Future task",
            status="pending",
            priority="low",
            due_date=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        test_db.add(task)
        test_db.flush()
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 0

    def test_no_due_date_not_marked(self, test_db: Session, owner_business: Business):
        task = Task(
            id=uuid4(),
            business_id=owner_business.id,
            title="No due date",
            status="pending",
            priority="low",
        )
        test_db.add(task)
        test_db.flush()
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 0

    def test_emits_overdue_event(self, test_db: Session, owner_business: Business):
        self._make_overdue_task(test_db, owner_business.id)
        service = FollowUpService(test_db)
        service.mark_overdue_tasks(owner_business.id)
        event = (
            test_db.query(Event)
            .filter(
                Event.business_id == owner_business.id,
                Event.event_type == EventType.TASK_OVERDUE,
            )
            .first()
        )
        assert event is not None

    def test_other_business_tasks_unaffected(self, test_db: Session, owner_business: Business, other_business: Business):
        self._make_overdue_task(test_db, other_business.id)
        service = FollowUpService(test_db)
        result = service.mark_overdue_tasks(owner_business.id)
        assert result == 0


# ── process_all ───────────────────────────────────────────────────────────────

class TestProcessAll:
    def test_returns_combined_summary(self, test_db: Session, owner_business: Business):
        service = FollowUpService(test_db)
        result = service.process_all(owner_business.id, idle_hours=24)
        assert "followup_tasks_created" in result
        assert "tasks_marked_overdue" in result
        assert result["followup_tasks_created"] == 0
        assert result["tasks_marked_overdue"] == 0


# ── FollowUpGlobalService ─────────────────────────────────────────────────────

class TestFollowUpGlobalService:
    def test_processes_all_businesses(self, test_db: Session, owner_business: Business, other_business: Business):
        service = FollowUpGlobalService(test_db)
        total = service.process_all_businesses(idle_hours=24)
        assert total == 0

    def test_counts_actions_across_businesses(self, test_db: Session, owner_business: Business, other_business: Business):
        _make_old_lead(test_db, owner_business.id, status="new", hours_old=48)
        _make_old_lead(test_db, other_business.id, status="new", hours_old=48)
        service = FollowUpGlobalService(test_db)
        total = service.process_all_businesses(idle_hours=24)
        assert total == 2
