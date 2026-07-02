"""Automated follow-up service.

Implements PRD section 3.3 — Automated Follow-Ups:
- Trigger reminders if no activity on leads
- Time-based automation (configurable thresholds)
- Create follow-up tasks automatically for idle leads
- Mark overdue tasks based on due dates
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.enums import EventStatus, EventType
from app.models.event import Event
from app.models.lead import Lead
from app.models.task import Task


logger = logging.getLogger(__name__)


class FollowUpService:
    """Automated follow-up automation for leads and tasks.
    
    This service runs periodically via Celery Beat to:
    1. Detect idle leads with no recent activity
    2. Create follow-up tasks for idle leads
    3. Mark overdue tasks past their due date
    4. Emit events for notification processing
    """

    def __init__(self, db: Session):
        self.db = db

    def process_idle_leads(
        self,
        business_id: UUID,
        idle_hours: int = 24,
    ) -> int:
        """Find leads with no recent activity and create follow-up tasks.
        
        A lead is considered idle if:
        - Status is 'new' or 'contacted' (active pipeline stages)
        - No events referencing it since `idle_hours` ago
        - No existing pending follow-up task already exists
        
        Args:
            business_id: Tenant ID
            idle_hours: Hours of inactivity before triggering follow-up
            
        Returns:
            Number of follow-up tasks created
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=idle_hours)
        
        # Get active leads that might need follow-up
        active_leads = (
            self.db.query(Lead)
            .filter(
                Lead.business_id == business_id,
                Lead.status.in_(["new", "contacted"]),
                Lead.updated_at < cutoff,
            )
            .all()
        )
        
        tasks_created = 0
        
        for lead in active_leads:
            # Check if there's recent activity via events
            recent_event = (
                self.db.query(Event)
                .filter(
                    Event.business_id == business_id,
                    Event.entity_type == "lead",
                    Event.entity_id == lead.id,
                    Event.created_at >= cutoff,
                )
                .first()
            )
            
            if recent_event is not None:
                continue
            
            # Check if a pending follow-up task already exists
            existing_followup = (
                self.db.query(Task)
                .filter(
                    Task.business_id == business_id,
                    Task.lead_id == lead.id,
                    Task.status.in_(["pending", "in_progress"]),
                    Task.title.ilike("%follow%up%"),
                )
                .first()
            )
            
            if existing_followup is not None:
                continue
            
            # Create follow-up task
            followup_task = Task(
                id=uuid4(),
                business_id=business_id,
                lead_id=lead.id,
                assigned_to=lead.assigned_to,
                title=f"Follow up: Lead {lead.id} idle for {idle_hours}h",
                description=(
                    f"This lead has been in '{lead.status}' status with no "
                    f"activity for {idle_hours} hours. Please follow up."
                ),
                status="pending",
                priority="high",
                due_date=datetime.now(timezone.utc) + timedelta(hours=4),
            )
            self.db.add(followup_task)
            
            # Emit event for the follow-up task creation
            followup_event = Event(
                id=uuid4(),
                business_id=business_id,
                event_type=EventType.TASK_CREATED,
                entity_type="task",
                entity_id=followup_task.id,
                description="Auto follow-up task created for idle lead",
                data={
                    "trigger": "idle_lead_followup",
                    "idle_hours": idle_hours,
                    "lead_id": str(lead.id),
                    "lead_status": lead.status,
                },
                status=EventStatus.PENDING,
            )
            self.db.add(followup_event)
            tasks_created += 1
        
        if tasks_created > 0:
            self.db.flush()
            logger.info(
                "Created %d follow-up tasks for idle leads (business=%s, idle_hours=%d)",
                tasks_created,
                business_id,
                idle_hours,
            )
        
        return tasks_created

    def mark_overdue_tasks(self, business_id: UUID) -> int:
        """Mark tasks past their due date as overdue.
        
        Only transitions tasks in 'pending' or 'in_progress' status.
        Completed tasks are never marked overdue.
        
        Args:
            business_id: Tenant ID
            
        Returns:
            Number of tasks marked overdue
        """
        now = datetime.now(timezone.utc)
        
        overdue_tasks = (
            self.db.query(Task)
            .filter(
                Task.business_id == business_id,
                Task.status.in_(["pending", "in_progress"]),
                Task.due_date.is_not(None),
                Task.due_date < now,
            )
            .all()
        )
        
        marked = 0
        for task in overdue_tasks:
            task.status = "overdue"
            
            # Emit event for overdue notification
            overdue_event = Event(
                id=uuid4(),
                business_id=business_id,
                event_type=EventType.TASK_OVERDUE,
                entity_type="task",
                entity_id=task.id,
                description=f"Task '{task.title}' is now overdue",
                data={
                    "trigger": "overdue_check",
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "assigned_to": str(task.assigned_to) if task.assigned_to else None,
                },
                status=EventStatus.PENDING,
            )
            self.db.add(overdue_event)
            marked += 1
        
        if marked > 0:
            self.db.flush()
            logger.info(
                "Marked %d tasks as overdue for business %s",
                marked,
                business_id,
            )
        
        return marked

    def process_all(
        self,
        business_id: UUID,
        idle_hours: int = 24,
    ) -> dict[str, int]:
        """Run all automated follow-up checks for a business.
        
        Args:
            business_id: Tenant ID
            idle_hours: Hours of inactivity threshold
            
        Returns:
            Summary of actions taken
        """
        followups = self.process_idle_leads(
            business_id=business_id,
            idle_hours=idle_hours,
        )
        overdue = self.mark_overdue_tasks(business_id=business_id)
        
        return {
            "followup_tasks_created": followups,
            "tasks_marked_overdue": overdue,
        }


class FollowUpGlobalService:
    """Cross-tenant follow-up processing for Celery Beat tasks."""

    def __init__(self, db: Session):
        self.db = db

    def process_all_businesses(
        self,
        idle_hours: int = 24,
    ) -> int:
        """Run follow-up checks across all active businesses.
        
        Returns total number of actions taken.
        """
        from app.models.business import Business
        
        businesses = self.db.query(Business).all()
        total_actions = 0
        
        for business in businesses:
            service = FollowUpService(self.db)
            result = service.process_all(
                business_id=business.id,
                idle_hours=idle_hours,
            )
            total_actions += sum(result.values())
        
        return total_actions
