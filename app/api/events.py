"""Event API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.event import EventAuditTrailResponse, EventCreate, EventListResponse, EventResponse
from app.services.event import EventService

router = APIRouter(
    prefix="/api/v1/events",
    tags=["events"],
)


@router.post("", response_model=EventResponse)
def create_event(
    data: EventCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Create event.
    
    Events are created automatically by services. This endpoint allows
    manual event creation for testing or external integrations.
    """
    service = EventService(db)
    try:
        return service.create(current_user.business_id, current_user, data)
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=EventListResponse)
def list_events(
    skip: int = 0,
    limit: int = 100,
    event_type: EventType | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    unprocessed_only: bool = False,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List events.
    
    Filter by event type, entity type/id, or show only unprocessed events
    (for workflow engine processing).
    """
    service = EventService(db)

    try:
        if unprocessed_only:
            events, total = service.list_unprocessed(current_user.business_id, current_user, skip=skip, limit=limit)
        elif entity_type and entity_id:
            events, total = service.list_by_entity(current_user.business_id, current_user, entity_type, entity_id, skip=skip, limit=limit)
        elif event_type:
            events, total = service.list_by_type(current_user.business_id, current_user, event_type, skip=skip, limit=limit)
        else:
            events, total = service.list(current_user.business_id, current_user, skip=skip, limit=limit)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return EventListResponse(
        items=[EventResponse.model_validate(event) for event in events],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Get event by ID."""
    service = EventService(db)
    event = service.get(current_user.business_id, current_user, event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.patch("/{event_id}", response_model=EventResponse)
def mark_event_dispatched(
    event_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Mark event as dispatched by workflow engine.
    
    🧨 RBAC: Only owner/manager can mark events as dispatched.
    """
    service = EventService(db)
    try:
        event = service.mark_dispatched(current_user.business_id, current_user, event_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


@router.get("/audit-trail/{entity_type}/{entity_id}", response_model=EventAuditTrailResponse)
def get_audit_trail(
    entity_type: str,
    entity_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int | None = None,
):
    """Get full audit trail for an entity (lead, task, customer).
    
    Returns all events related to the entity with full metadata.
    Useful for understanding what happened to a lead/task over time.
    """
    service = EventService(db)
    return service.get_audit_trail(
        current_user.business_id,
        current_user,
        entity_type,
        entity_id,
        skip=skip,
        limit=limit,
    )
