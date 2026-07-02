"""Event repository - data access layer."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventStatus, EventType
from app.models.event import Event
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    """Event repository with business_id filtering.
    
    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        """Initialize repository."""
        super().__init__(db, Event)

    def get_by_event_type(
        self, business_id: UUID, event_type: EventType, skip: int = 0, limit: int = 100
    ) -> list[Event]:
        """Get events by type within business.
        
        🧨 CRITICAL: Filters by business_id to prevent data leaks.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.event_type == event_type,
        ).order_by(Event.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_event_type(self, business_id: UUID, event_type: EventType) -> int:
        """Count events by type within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.event_type == event_type,
        ).count()

    def get_by_entity(self, business_id: UUID, entity_type: str, entity_id: UUID, skip: int = 0, limit: int = 100) -> list[Event]:
        """Get events for entity within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.entity_type == entity_type,
            Event.entity_id == entity_id,
        ).order_by(Event.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_entity(self, business_id: UUID, entity_type: str, entity_id: UUID) -> int:
        """Count events for entity within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.entity_type == entity_type,
            Event.entity_id == entity_id,
        ).count()

    def get_unprocessed(self, business_id: UUID, skip: int = 0, limit: int = 100) -> list[Event]:
        """Get unprocessed events within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.status == EventStatus.PENDING,
        ).order_by(Event.created_at.asc()).offset(skip).limit(limit).all()

    def count_unprocessed(self, business_id: UUID) -> int:
        """Count unprocessed events within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.status == EventStatus.PENDING,
        ).count()

    def get_by_actor(self, business_id: UUID, actor_id: UUID, skip: int = 0, limit: int = 100) -> list[Event]:
        """Get events triggered by user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.actor_id == actor_id,
        ).order_by(Event.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_actor(self, business_id: UUID, actor_id: UUID) -> int:
        """Count events triggered by user within business.
        
        🧨 CRITICAL: Filters by business_id.
        """
        return self.db.query(Event).filter(
            Event.business_id == business_id,
            Event.actor_id == actor_id,
        ).count()

    def claim_oldest_pending(self, business_id: UUID, worker_id: str) -> Event | None:
        """Claim the oldest pending event for processing.
        
        Caller owns transaction boundaries and commit/rollback.
        """
        event = (
            self.db.query(Event)
            .filter(
                Event.business_id == business_id,
                Event.status == EventStatus.PENDING,
            )
            .order_by(Event.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if not event:
            return None

        event.status = EventStatus.CLAIMED
        event.locked_at = datetime.now(timezone.utc)
        event.claimed_by = worker_id
        self.db.flush()
        return event

    def release_stale_claims(self, business_id: UUID, stale_after_minutes: int = 10) -> int:
        """Release events stuck in claimed state past the staleness threshold.
        
        Caller owns transaction boundaries and commit/rollback.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
        rows_updated = (
            self.db.query(Event)
            .filter(
                Event.business_id == business_id,
                Event.status == EventStatus.CLAIMED,
                Event.locked_at.is_not(None),
                Event.locked_at < cutoff,
            )
            .update(
                {
                    Event.status: EventStatus.PENDING,
                    Event.locked_at: None,
                    Event.claimed_by: None,
                },
                synchronize_session=False,
            )
        )
        return int(rows_updated or 0)
