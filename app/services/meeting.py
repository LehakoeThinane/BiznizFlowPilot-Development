"""Meeting service - scheduling, invites, and Agora call-token minting."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import EventType
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.user import User
from app.repositories.meeting import MeetingRepository
from app.schemas.auth import CurrentUser
from app.schemas.meeting import MeetingCreate, MeetingUpdate

logger = logging.getLogger(__name__)

_AGORA_ROLE_PUBLISHER = 1


def derive_agora_uid(user_id: UUID) -> int:
    """Deterministic uint32 Agora uid from a user's UUID (first 32 bits of the hex).

    Lets any participant compute another participant's uid client-side from
    their user_id alone, without the backend needing to store/broadcast a
    separate uid mapping.
    """
    return (int(user_id.hex[:8], 16) % 2_147_483_646) + 1


class MeetingService:
    """Meeting service with RBAC and Agora call-token minting.

    🧨 RBAC: Any authenticated user can schedule a meeting. Only the
    organizer can reschedule/cancel/start/end. Invitees can accept/decline
    their own invite. Organizer + accepted/pending invitees can join.

    Auto-emits events on schedule/update/cancel/start when event_service is provided.
    """

    def __init__(self, db: Session, event_service=None):
        self.db = db
        self.repo = MeetingRepository(db)
        self._event_service = event_service

    def _emit_event(
        self,
        event_type: EventType,
        business_id: UUID,
        entity_id: UUID,
        actor_id: UUID | None = None,
        description: str | None = None,
        data: dict | None = None,
    ) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.create_event(
                business_id=business_id,
                event_type=event_type,
                entity_type="meeting",
                entity_id=entity_id,
                actor_id=actor_id,
                description=description,
                data=data,
            )
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.warning("Failed to emit %s event for meeting %s", event_type.value, entity_id, exc_info=True)

    def _notify_users(self, business_id: UUID, user_ids: list[UUID], title: str, message: str, meeting_id: UUID) -> None:
        """Insert a Notification per specific user_id, regardless of role.

        Meeting invites target the people actually invited, not a role
        cohort, so this bypasses notify_business()'s role-based fan-out.
        """
        for user_id in user_ids:
            self.db.add(Notification(
                id=uuid4(),
                business_id=business_id,
                user_id=user_id,
                type="meeting",
                title=title,
                message=message,
                action_url=f"/calendar?meeting={meeting_id}",
                related_type="meeting",
                related_id=meeting_id,
            ))

    def create(self, business_id: UUID, current_user: CurrentUser, data: MeetingCreate) -> Meeting:
        invitee_ids = set(data.participant_user_ids)
        found = (
            self.db.query(User.id)
            .filter(User.business_id == business_id, User.id.in_(invitee_ids), User.is_active.is_(True))
            .all()
        )
        found_ids = {row[0] for row in found}
        missing = invitee_ids - found_ids
        if missing:
            raise ValueError(f"Unknown or inactive user(s): {', '.join(str(m) for m in missing)}")

        meeting_id = uuid4()
        meeting = Meeting(
            id=meeting_id,
            business_id=business_id,
            organizer_id=current_user.user_id,
            title=data.title,
            description=data.description,
            start_time=data.start_time,
            end_time=data.end_time,
            call_type=data.call_type,
            status="scheduled",
            agora_channel_name=f"meeting-{meeting_id}",
        )
        self.db.add(meeting)
        self.db.flush()

        self.repo.add_participant(meeting_id, current_user.user_id, response_status="accepted")
        for user_id in invitee_ids:
            if user_id == current_user.user_id:
                continue
            self.repo.add_participant(meeting_id, user_id, response_status="pending")

        self._notify_users(
            business_id, [uid for uid in invitee_ids if uid != current_user.user_id],
            "Meeting invite",
            f"{current_user.full_name} invited you to \"{data.title}\" at {data.start_time.isoformat()}.",
            meeting_id,
        )

        self.db.commit()
        self.db.refresh(meeting)

        self._emit_event(
            event_type=EventType.MEETING_SCHEDULED,
            business_id=business_id,
            entity_id=meeting.id,
            actor_id=current_user.user_id,
            description=f"Meeting scheduled: '{meeting.title}'",
            data={"call_type": meeting.call_type, "participant_count": len(invitee_ids)},
        )
        return meeting

    def get(self, business_id: UUID, meeting_id: UUID) -> Meeting | None:
        return self.repo.get(business_id=business_id, entity_id=meeting_id)

    def list_mine(self, business_id: UUID, current_user: CurrentUser, skip: int = 0, limit: int = 20) -> tuple[list[Meeting], int]:
        meetings = self.repo.list_for_participant(business_id, current_user.user_id, skip, limit)
        total = self.repo.count_for_participant(business_id, current_user.user_id)
        return meetings, total

    def list_active(self, business_id: UUID, current_user: CurrentUser) -> list[Meeting]:
        return self.repo.list_active_for_user(business_id, current_user.user_id)

    def update(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID, data: MeetingUpdate) -> Meeting | None:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        if meeting.organizer_id != current_user.user_id:
            raise ValueError("Permission denied: Only the organizer can modify this meeting")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(meeting, key, value)
        self.db.commit()
        self.db.refresh(meeting)

        participant_ids = [p.user_id for p in meeting.participants if p.user_id != current_user.user_id]
        if data.status == "cancelled":
            self._notify_users(
                business_id, participant_ids, "Meeting cancelled",
                f"\"{meeting.title}\" has been cancelled.", meeting.id,
            )
            self.db.commit()
            self._emit_event(
                EventType.MEETING_CANCELLED, business_id, meeting.id, current_user.user_id,
                description=f"Meeting cancelled: '{meeting.title}'",
            )
        else:
            self._notify_users(
                business_id, participant_ids, "Meeting updated",
                f"\"{meeting.title}\" has been updated.", meeting.id,
            )
            self.db.commit()
            self._emit_event(
                EventType.MEETING_UPDATED, business_id, meeting.id, current_user.user_id,
                description=f"Meeting updated: '{meeting.title}'",
                data={"updated_fields": list(update_data.keys())},
            )
        return meeting

    def respond(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID, response_status: str) -> Meeting | None:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        participant = self.repo.get_participant(meeting_id, current_user.user_id)
        if not participant:
            raise ValueError("Permission denied: You are not invited to this meeting")
        participant.response_status = response_status
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def start_call(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID) -> Meeting | None:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        if meeting.organizer_id != current_user.user_id:
            raise ValueError("Permission denied: Only the organizer can start this call")
        meeting.status = "in_progress"
        self.db.commit()
        self.db.refresh(meeting)

        participant_ids = [p.user_id for p in meeting.participants if p.user_id != current_user.user_id]
        self._notify_users(
            business_id, participant_ids, "Call starting",
            f"{current_user.full_name} started the call for \"{meeting.title}\".", meeting.id,
        )
        self.db.commit()
        self._emit_event(
            EventType.MEETING_STARTED, business_id, meeting.id, current_user.user_id,
            description=f"Meeting call started: '{meeting.title}'",
        )
        return meeting

    def end_call(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID) -> Meeting | None:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        if meeting.organizer_id != current_user.user_id:
            raise ValueError("Permission denied: Only the organizer can end this call")
        meeting.status = "completed"
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def generate_join_token(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID) -> dict:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        is_organizer = meeting.organizer_id == current_user.user_id
        participant = self.repo.get_participant(meeting_id, current_user.user_id)
        if not is_organizer and not participant:
            raise ValueError("Permission denied: You are not invited to this meeting")

        if not settings.agora_app_id or not settings.agora_app_certificate:
            raise LookupError("Voice/video calling is not configured. Set AGORA_APP_ID and AGORA_APP_CERTIFICATE.")

        from agora_token_builder import RtcTokenBuilder

        uid = derive_agora_uid(current_user.user_id)
        expire_ts = int(time.time()) + settings.agora_token_expiration_seconds
        token = RtcTokenBuilder.buildTokenWithUid(
            settings.agora_app_id,
            settings.agora_app_certificate,
            meeting.agora_channel_name,
            uid,
            _AGORA_ROLE_PUBLISHER,
            expire_ts,
        )

        if participant is not None:
            participant.joined_at = datetime.now(timezone.utc)
            self.db.commit()

        return {
            "agora_app_id": settings.agora_app_id,
            "channel_name": meeting.agora_channel_name,
            "token": token,
            "uid": uid,
            "expires_at": datetime.fromtimestamp(expire_ts, tz=timezone.utc),
        }
