"""Event tests - creation, processing, audit trail, multi-tenant isolation."""

import pytest
from uuid import uuid4
from sqlalchemy.orm import Session

from app.core.enums import EventStatus, EventType
from app.models.event import Event
from app.repositories.event import EventRepository
from app.schemas.auth import CurrentUser
from app.schemas.event import EventCreate
from app.services.event import EventService


class TestEventCreate:
    """Test event creation."""

    def test_create_event_via_service(self, test_db: Session, owner_user: CurrentUser):
        """Service can create events."""
        service = EventService(test_db)
        data = EventCreate(
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
            description="New lead from web form",
        )

        event = service.create(owner_user.business_id, owner_user, data)

        assert event.event_type == EventType.LEAD_CREATED
        assert event.entity_type == "lead"
        assert event.actor_id == owner_user.user_id
        assert event.business_id == owner_user.business_id

    def test_create_event_internal(self, test_db: Session, owner_user: CurrentUser):
        """Services can emit events without request context."""
        service = EventService(test_db)
        entity_id = uuid4()

        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_ASSIGNED,
            entity_type="task",
            entity_id=entity_id,
            actor_id=owner_user.user_id,
            description="Task assigned to John",
            data={"assigned_to": str(uuid4()), "due_date": "2026-05-01"},
        )

        assert event.event_type == EventType.TASK_ASSIGNED
        assert event.status == EventStatus.PENDING
        assert event.data["assigned_to"]


class TestEventRead:
    """Test event retrieval."""

    def test_get_event(self, test_db: Session, owner_user: CurrentUser):
        """Get event by ID."""
        service = EventService(test_db)
        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            entity_type="lead",
            entity_id=uuid4(),
        )
        test_db.commit()

        retrieved = service.get(owner_user.business_id, owner_user, event.id)

        assert retrieved.id == event.id
        assert retrieved.event_type == EventType.LEAD_STATUS_CHANGED

    def test_list_events(self, test_db: Session, owner_user: CurrentUser):
        """List events."""
        service = EventService(test_db)
        
        # Create multiple events
        for i in range(3):
            service.create_event(
                business_id=owner_user.business_id,
                event_type=EventType.LEAD_CREATED,
                entity_type="lead",
                entity_id=uuid4(),
            )
        test_db.commit()

        events, total = service.list(owner_user.business_id, owner_user)

        assert total >= 3
        assert len(events) >= 3

    def test_list_by_event_type(self, test_db: Session, owner_user: CurrentUser):
        """List events by type."""
        service = EventService(test_db)

        # Create events of different types
        for _ in range(2):
            service.create_event(
                business_id=owner_user.business_id,
                event_type=EventType.LEAD_CREATED,
                entity_type="lead",
                entity_id=uuid4(),
            )
        service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_COMPLETED,
            entity_type="task",
            entity_id=uuid4(),
        )
        test_db.commit()

        events, total = service.list_by_type(owner_user.business_id, owner_user, EventType.LEAD_CREATED)

        assert total >= 2
        assert all(e.event_type == EventType.LEAD_CREATED for e in events)

    def test_list_by_entity(self, test_db: Session, owner_user: CurrentUser):
        """List events for specific entity (audit trail)."""
        service = EventService(test_db)
        entity_id = uuid4()

        # Create multiple event types for same entity
        event_types = [
            EventType.LEAD_CREATED,
            EventType.LEAD_STATUS_CHANGED,
            EventType.TASK_CREATED,
        ]
        for event_type in event_types:
            service.create_event(
                business_id=owner_user.business_id,
                event_type=event_type,
                entity_type="lead",
                entity_id=entity_id,
            )
        test_db.commit()

        events, total = service.list_by_entity(owner_user.business_id, owner_user, "lead", entity_id)

        assert total == 3
        assert all(e.entity_id == entity_id for e in events)


class TestEventProcessing:
    """Test event processing workflow."""

    def test_list_unprocessed_events(self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser):
        """List unprocessed events for workflow engine."""
        service = EventService(test_db)

        # Create unprocessed events
        for _ in range(2):
            service.create_event(
                business_id=owner_user.business_id,
                event_type=EventType.LEAD_CREATED,
                entity_type="lead",
                entity_id=uuid4(),
            )
        test_db.commit()

        # Owner/Manager can list unprocessed
        events, total = service.list_unprocessed(owner_user.business_id, owner_user)
        assert total >= 2

        events, total = service.list_unprocessed(manager_user.business_id, manager_user)
        assert isinstance(events, list)

    def test_unprocessed_list_rbac(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot access unprocessed events."""
        service = EventService(test_db)

        with pytest.raises(PermissionError, match="cannot view unprocessed events"):
            service.list_unprocessed(staff_user.business_id, staff_user)

    def test_mark_processed(self, test_db: Session, owner_user: CurrentUser):
        """Mark event as dispatched."""
        service = EventService(test_db)
        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.WORKFLOW_TRIGGERED,
            entity_type="lead",
            entity_id=uuid4(),
        )
        test_db.commit()

        # Initially not processed
        assert event.status == EventStatus.PENDING

        # Mark as dispatched
        updated = service.mark_processed(owner_user.business_id, owner_user, event.id)

        assert updated.status == EventStatus.DISPATCHED
        assert updated.processed is True

    def test_mark_processed_rbac(self, test_db: Session, staff_user: CurrentUser):
        """Staff cannot mark events as dispatched."""
        service = EventService(test_db)

        with pytest.raises(PermissionError, match="cannot mark events as dispatched"):
            service.mark_processed(staff_user.business_id, staff_user, uuid4())

    def test_claim_process_commit_cycle(self, test_db: Session, owner_user: CurrentUser):
        """Worker-style claim -> process -> commit flow preserves transaction boundaries."""
        service = EventService(test_db)
        repo = EventRepository(test_db)

        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=uuid4(),
        )
        test_db.commit()

        # Claim without commit and ensure rollback returns the event to pending.
        claimed = repo.claim_oldest_pending(owner_user.business_id, worker_id="worker-1")
        assert claimed is not None
        assert claimed.status == EventStatus.CLAIMED
        assert claimed.claimed_by == "worker-1"
        test_db.rollback()

        rolled_back = repo.get(owner_user.business_id, event.id)
        assert rolled_back.status == EventStatus.PENDING
        assert rolled_back.claimed_by is None
        assert rolled_back.locked_at is None

        # Claim again, process, then commit once for the full worker cycle.
        claimed = repo.claim_oldest_pending(owner_user.business_id, worker_id="worker-1")
        claimed.status = EventStatus.DISPATCHED
        claimed.claimed_by = None
        claimed.locked_at = None
        test_db.commit()

        processed = repo.get(owner_user.business_id, event.id)
        assert processed.status == EventStatus.DISPATCHED
        assert processed.processed is True


class TestAuditTrail:
    """Test audit trail functionality."""

    def test_get_audit_trail(self, test_db: Session, owner_user: CurrentUser):
        """Get complete audit trail for entity."""
        service = EventService(test_db)
        entity_id = uuid4()

        # Create events for entity
        service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=entity_id,
            description="Lead created from web form",
        )
        service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            entity_type="lead",
            entity_id=entity_id,
            description="Status changed to contacted",
            data={"old_status": "new", "new_status": "contacted"},
        )
        test_db.commit()

        trail = service.get_audit_trail(owner_user.business_id, owner_user, "lead", entity_id)

        assert trail["entity_type"] == "lead"
        assert trail["entity_id"] == entity_id
        assert trail["event_count"] == 2
        assert len(trail["events"]) == 2


class TestEventMultiTenancy:
    """Test multi-tenant isolation."""

    def test_event_isolation_across_businesses(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        """Event from one business not visible to another."""
        service = EventService(test_db)
        entity_id = uuid4()

        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_CREATED,
            entity_type="lead",
            entity_id=entity_id,
        )
        test_db.commit()

        # Owner can see their event
        retrieved = service.get(owner_user.business_id, owner_user, event.id)
        assert retrieved is not None

        # Other business cannot see it
        retrieved = service.get(other_user.business_id, other_user, event.id)
        assert retrieved is None

    def test_list_only_own_business_events(self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        """List only returns events from user's business."""
        service = EventService(test_db)

        # Owner creates event
        service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.TASK_CREATED,
            entity_type="task",
            entity_id=uuid4(),
        )
        test_db.commit()

        # Owner sees their event
        events, total = service.list(owner_user.business_id, owner_user)
        assert total >= 1

        # Other user doesn't see it
        events, total = service.list(other_user.business_id, other_user)
        assert total == 0


class TestEventData:
    """Test event metadata storage."""

    def test_event_with_metadata(self, test_db: Session, owner_user: CurrentUser):
        """Events can store arbitrary metadata."""
        service = EventService(test_db)
        metadata = {
            "old_status": "new",
            "new_status": "contacted",
            "assigned_to": "john@example.com",
            "notes": "Customer called back",
        }

        event = service.create_event(
            business_id=owner_user.business_id,
            event_type=EventType.LEAD_STATUS_CHANGED,
            entity_type="lead",
            entity_id=uuid4(),
            data=metadata,
        )
        test_db.commit()

        retrieved = service.get(owner_user.business_id, owner_user, event.id)

        assert retrieved.data == metadata
        assert retrieved.data["old_status"] == "new"
