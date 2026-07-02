"""Event service - event creation and processing."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import EventStatus, EventType
from app.core.permissions import PRIVILEGED_ROLES, require_role
from app.models.event import Event
from app.repositories.event import EventRepository
from app.schemas.auth import CurrentUser
from app.schemas.event import EventCreate


class EventService:
    """Event service with event creation and processing.
    
    Events are the foundation for the workflow orchestration system.
    All business actions (lead created, task assigned, etc.) create events.
    Events are then processed asynchronously by the workflow engine.
    """

    def __init__(self, db: Session):
        """Initialize service."""
        self.db = db
        self.repo = EventRepository(db)

    def create(self, business_id: UUID, current_user: CurrentUser, data: EventCreate) -> Event:
        """Create event.
        
        Events are created automatically by services when business actions occur.
        Can also be created manually via API.
        """
        payload = data.model_dump(exclude={"actor_id"})
        return self.create_event(
            business_id=business_id,
            actor_id=current_user.user_id if current_user else data.actor_id,
            **payload,
        )

    def create_event(
        self,
        business_id: UUID,
        event_type: EventType | str,
        entity_type: str,
        entity_id: UUID,
        actor_id: Optional[UUID] = None,
        description: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
        status: EventStatus = EventStatus.PENDING,
    ) -> Event:
        """Create event from internal service methods.
        
        Called by other services (LeadService, TaskService) when business actions occur.
        This allows services to emit events without requiring a request context.
        """
        normalized_event_type = EventType(event_type) if isinstance(event_type, str) else event_type
        return self.repo.create(
            business_id=business_id,
            event_type=normalized_event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            data=data,
            status=status,
            locked_at=None,
            claimed_by=None,
        )

    def get(self, business_id: UUID, current_user: CurrentUser, event_id: UUID) -> Event | None:
        """Get event by ID.
        
        🧨 All roles can view events in their business.
        """
        return self.repo.get(business_id=business_id, entity_id=event_id)

    def list(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Event], int]:
        """List events.
        
        🧨 All roles can view events in their business.
        """
        events = self.repo.list(business_id=business_id, skip=skip, limit=limit)
        total = self.repo.count(business_id=business_id)
        return events, total

    def list_by_type(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        event_type: EventType | str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Event], int]:
        """List events by type.
        
        🧨 All roles can view events.
        """
        normalized_event_type = EventType(event_type) if isinstance(event_type, str) else event_type
        events = self.repo.get_by_event_type(
            business_id=business_id,
            event_type=normalized_event_type,
            skip=skip,
            limit=limit,
        )
        total = self.repo.count_by_event_type(business_id=business_id, event_type=normalized_event_type)
        return events, total

    def list_by_entity(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        entity_type: str,
        entity_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Event], int]:
        """List events for entity (lead, task, etc.).
        
        🧨 Useful for viewing audit trail of a specific lead or task.
        """
        events = self.repo.get_by_entity(business_id=business_id, entity_type=entity_type, entity_id=entity_id, skip=skip, limit=limit)
        total = self.repo.count_by_entity(business_id=business_id, entity_type=entity_type, entity_id=entity_id)
        return events, total

    def list_unprocessed(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 100) -> tuple[list[Event], int]:
        """List unprocessed events (for workflow engine).
        
        🧨 RBAC: Only owner/manager can access unprocessed events.
        """
        require_role(current_user, PRIVILEGED_ROLES, "view unprocessed events")

        events = self.repo.get_unprocessed(business_id=business_id, skip=skip, limit=limit)
        total = self.repo.count_unprocessed(business_id=business_id)
        return events, total

    def mark_dispatched(self, business_id: UUID, current_user: CurrentUser, event_id: UUID) -> Event | None:
        """Mark event as dispatched by workflow engine.
        
        🧨 RBAC: Only owner/manager can mark events as dispatched.
        """
        require_role(current_user, PRIVILEGED_ROLES, "mark events as dispatched")

        event = self.repo.get(business_id=business_id, entity_id=event_id)
        if not event:
            return None

        return self.repo.update(
            business_id=business_id,
            entity_id=event_id,
            status=EventStatus.DISPATCHED,
            locked_at=None,
            claimed_by=None,
        )

    def mark_processed(self, business_id: UUID, current_user: CurrentUser, event_id: UUID) -> Event | None:
        """Backward-compatible alias for legacy callers."""
        return self.mark_dispatched(
            business_id=business_id,
            current_user=current_user,
            event_id=event_id,
        )

    def claim_next_event(self, business_id: UUID, worker_id: str) -> Event | None:
        """Claim the oldest pending event for async processing."""
        return self.repo.claim_oldest_pending(business_id=business_id, worker_id=worker_id)

    def release_stale_claims(self, business_id: UUID, stale_after_minutes: int = 10) -> int:
        """Release stale claimed events for recovery workflows."""
        return self.repo.release_stale_claims(
            business_id=business_id,
            stale_after_minutes=stale_after_minutes,
        )

    def get_audit_trail(
        self,
        business_id: UUID,
        current_user: CurrentUser,
        entity_type: str,
        entity_id: UUID,
        skip: int = 0,
        limit: int | None = None,
    ) -> dict:
        """Get full audit trail for an entity.
        
        Returns all events related to a lead/task with full metadata.
        """
        requested_limit = settings.audit_trail_default_limit if limit is None else limit
        safe_limit = max(1, min(requested_limit, settings.audit_trail_max_limit))
        events, total = self.list_by_entity(
            business_id=business_id,
            current_user=current_user,
            entity_type=entity_type,
            entity_id=entity_id,
            skip=skip,
            limit=safe_limit,
        )
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_count": total,
            "skip": skip,
            "limit": safe_limit,
            "events": events,
        }
