"""Public (unauthenticated) meeting RSVP endpoints - the accept/decline
link an external invitee actually clicks from their invite email. No auth
dependency on purpose (mirrors app/api/document_share.py's public_router):
the token itself is the credential, and this must stay reachable even if
the inviting org's trial has expired."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.meeting import MeetingRsvpDetailOut, MeetingRsvpRespondRequest
from app.services.meeting import MeetingService

public_router = APIRouter(tags=["meeting-rsvp-public"])
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, in_memory_fallback_enabled=True)


def _to_rsvp_detail(participant) -> MeetingRsvpDetailOut:
    meeting = participant.meeting
    return MeetingRsvpDetailOut(
        title=meeting.title,
        description=meeting.description,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        call_type=meeting.call_type,
        organizer_name=meeting.organizer.full_name if meeting.organizer else "",
        response_status=participant.response_status,
    )


@public_router.get("/api/v1/meeting-rsvp/{token}", response_model=MeetingRsvpDetailOut, include_in_schema=False)
@limiter.limit("20/minute")
def get_meeting_rsvp_details(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    """No-auth pre-check for the RSVP landing page - meeting details + current response status."""
    service = MeetingService(db)
    try:
        participant = service.get_external_participant_by_token(token)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_rsvp_detail(participant)


@public_router.post(
    "/api/v1/meeting-rsvp/{token}/respond", response_model=MeetingRsvpDetailOut, include_in_schema=False
)
@limiter.limit("10/minute")
def respond_to_meeting_rsvp(
    token: str, body: MeetingRsvpRespondRequest, request: Request, db: Annotated[Session, Depends(get_db)]
):
    """Accept or decline a meeting invite via its token. No account/login required."""
    service = MeetingService(db)
    try:
        participant = service.respond_external(token, body.response_status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_rsvp_detail(participant)
