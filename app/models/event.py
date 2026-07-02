"""Event model - audit and workflow trigger tracking."""

from sqlalchemy import Column, DateTime, Enum as SAEnum, Index, JSON, ForeignKey, String, Uuid

from app.core.enums import EventStatus, EventType
from app.models.base import BaseModel, enum_values


class Event(BaseModel):
    """Event entity.

    Tracks all business actions (lead created, task assigned, etc.)
    for audit logging and workflow orchestration.
    Belongs to a business (multi-tenant).
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_business_id_status", "business_id", "status"),
    )

    business_id = Column(
        Uuid,
        nullable=False,
        index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )

    actor_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="User who triggered the event",
    )

    event_type = Column(
        SAEnum(EventType, name="event_type_enum", values_callable=enum_values),
        nullable=False,
        index=True,
        doc="Canonical event type for workflow triggers",
    )

    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Entity type: lead, task, customer, workflow_run",
    )

    entity_id = Column(
        Uuid,
        nullable=False,
        index=True,
        doc="ID of the entity that triggered the event",
    )

    description = Column(
        String(500),
        nullable=True,
        doc="Human-readable event description",
    )

    data = Column(
        JSON,
        nullable=True,
        doc="Event metadata (old status, new status, assigned user, etc.)",
    )

    status = Column(
        SAEnum(EventStatus, name="event_status", values_callable=enum_values),
        nullable=False,
        default=EventStatus.PENDING,
        server_default=EventStatus.PENDING.value,
        index=True,
        doc="Workflow processing state: pending, claimed, dispatched, failed",
    )

    locked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="When a worker claimed this event",
    )

    claimed_by = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Worker identifier that claimed this event",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Event id={self.id} type='{self.event_type}' status='{self.status}'>"

    @property
    def processed(self) -> bool:
        """Backward-compatible processed flag derived from status."""
        return self.status == EventStatus.DISPATCHED
