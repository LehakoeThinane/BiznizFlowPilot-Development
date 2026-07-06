"""Meeting scheduling & Agora call API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ConcurrencyConflictError
from app.dependencies import get_current_user
from app.models.meeting import Meeting
from app.schemas.auth import CurrentUser
from app.schemas.meeting import (
    AgoraJoinResponse,
    MeetingCreate,
    MeetingListResponse,
    MeetingOut,
    MeetingParticipantOut,
    MeetingRespondRequest,
    MeetingUpdate,
)
from app.services.event import EventService
from app.services.meeting import MeetingService

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


def _meeting_service(db: Session) -> MeetingService:
    return MeetingService(db, event_service=EventService(db))


def _meeting_out(meeting: Meeting) -> MeetingOut:
    out = MeetingOut.model_validate(meeting)
    out.organizer_name = meeting.organizer.full_name if meeting.organizer else ""
    out.participants = [
        MeetingParticipantOut(
            user_id=p.user_id,
            full_name=p.user.full_name if p.user else "",
            email=p.user.email if p.user else None,
            response_status=p.response_status,
            joined_at=p.joined_at,
        )
        for p in meeting.participants
    ]
    return out


@router.post("", response_model=MeetingOut, status_code=201)
def create_meeting(
    data: MeetingCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        meeting = service.create(current_user.business_id, current_user, data)
        return _meeting_out(meeting)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=MeetingListResponse)
def list_meetings(
    skip: int = 0,
    limit: int = 20,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    service = _meeting_service(db)
    meetings, total = service.list_mine(current_user.business_id, current_user, skip=skip, limit=limit)
    return MeetingListResponse(
        items=[_meeting_out(m) for m in meetings], total=total, skip=skip, limit=limit,
    )


@router.get("/active", response_model=list[MeetingOut])
def list_active_meetings(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """In-progress meetings the current user organizes or is invited to — polled for incoming-call UI."""
    service = _meeting_service(db)
    meetings = service.list_active(current_user.business_id, current_user)
    return [_meeting_out(m) for m in meetings]


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    meeting_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    service = _meeting_service(db)
    meeting = service.get(current_user.business_id, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return _meeting_out(meeting)


@router.patch("/{meeting_id}", response_model=MeetingOut)
def update_meeting(
    meeting_id: UUID,
    data: MeetingUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        meeting = service.update(current_user.business_id, current_user, meeting_id, data)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return _meeting_out(meeting)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConcurrencyConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/respond", response_model=MeetingOut)
def respond_to_meeting(
    meeting_id: UUID,
    data: MeetingRespondRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        meeting = service.respond(current_user.business_id, current_user, meeting_id, data.response_status)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return _meeting_out(meeting)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/start", response_model=MeetingOut)
def start_meeting_call(
    meeting_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        meeting = service.start_call(current_user.business_id, current_user, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return _meeting_out(meeting)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConcurrencyConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/end", response_model=MeetingOut)
def end_meeting_call(
    meeting_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        meeting = service.end_call(current_user.business_id, current_user, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return _meeting_out(meeting)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConcurrencyConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{meeting_id}/join", response_model=AgoraJoinResponse)
def join_meeting_call(
    meeting_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        service = _meeting_service(db)
        result = service.generate_join_token(current_user.business_id, current_user, meeting_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return AgoraJoinResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
