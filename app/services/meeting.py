"""Meeting service - scheduling, invites, and Agora call-token minting."""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.enums import EventType
from app.core.exceptions import ConcurrencyConflictError
from app.models.meeting import Meeting, MeetingExternalParticipant
from app.models.notification import Notification
from app.repositories.meeting import MeetingRepository
from app.repositories.user import UserRepository
from app.schemas.auth import CurrentUser
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.services.email import send_meeting_cancelled_email, send_meeting_invite_email, send_meeting_update_email
from app.utils.ics import build_meeting_ics
from app.utils.logger import get_logger

logger = get_logger(__name__)

_AGORA_ROLE_PUBLISHER = 1
_RSVP_TOKEN_VALIDITY_DAYS_AFTER_MEETING = 1


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


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
        """Queue an event row in the same (not-yet-committed) transaction as
        the caller's pending business-row change - the caller commits once,
        after this call, so both persist atomically or neither does."""
        if self._event_service is None:
            return
        self._event_service.create_event(
            business_id=business_id,
            event_type=event_type,
            entity_type="meeting",
            entity_id=entity_id,
            actor_id=actor_id,
            description=description,
            data=data,
            commit=False,
        )

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
        found_users = UserRepository(self.db).list_active_by_ids(business_id, invitee_ids)
        found_ids = {u.id for u in found_users}
        internal_emails = {u.email.lower() for u in found_users if u.email}
        missing = invitee_ids - found_ids
        if missing:
            raise ValueError(f"Unknown or inactive user(s): {', '.join(str(m) for m in missing)}")

        # Normalize + dedupe external emails, and drop any that already match
        # an invited internal user - no double-inviting the same person.
        external_emails = sorted({e.lower() for e in data.external_emails} - internal_emails)

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

        expires_at = data.end_time + timedelta(days=_RSVP_TOKEN_VALIDITY_DAYS_AFTER_MEETING)
        pending_invites: list[tuple[str, str]] = []  # (email, raw_token)
        for email in external_emails:
            raw_token = secrets.token_urlsafe(32)
            self.repo.add_external_participant(meeting_id, email, _hash_token(raw_token), expires_at)
            pending_invites.append((email, raw_token))

        self._notify_users(
            business_id, [uid for uid in invitee_ids if uid != current_user.user_id],
            "Meeting invite",
            f"{current_user.full_name} invited you to \"{data.title}\" at {data.start_time.isoformat()}.",
            meeting_id,
        )

        self._emit_event(
            event_type=EventType.MEETING_SCHEDULED,
            business_id=business_id,
            entity_id=meeting.id,
            actor_id=current_user.user_id,
            description=f"Meeting scheduled: '{meeting.title}'",
            data={
                "call_type": meeting.call_type,
                "participant_count": len(invitee_ids),
                "external_participant_count": len(external_emails),
            },
        )

        self.db.commit()
        self.db.refresh(meeting)

        for email, raw_token in pending_invites:
            try:
                self._send_external_invite_email(meeting, current_user, email, raw_token)
            except Exception:
                logger.exception("Failed to send meeting invite email to %s", email)

        return meeting

    def _rsvp_urls(self, raw_token: str) -> tuple[str, str]:
        base = f"{settings.frontend_url}/meeting-rsvp/{raw_token}"
        return f"{base}?action=accept", f"{base}?action=decline"

    def _send_external_invite_email(
        self, meeting: Meeting, organizer: CurrentUser, email: str, raw_token: str
    ) -> None:
        ics = build_meeting_ics(
            meeting_id=meeting.id, title=meeting.title, description=meeting.description,
            start_time=meeting.start_time, end_time=meeting.end_time,
            organizer_email=organizer.email, organizer_name=organizer.full_name,
            attendee_email=email, sequence=meeting.version, method="REQUEST",
        )
        accept_url, decline_url = self._rsvp_urls(raw_token)
        send_meeting_invite_email(
            to_email=email, meeting_title=meeting.title, start_time_str=meeting.start_time.isoformat(),
            organizer_name=organizer.full_name, accept_url=accept_url, decline_url=decline_url,
            ics_bytes=ics, db=self.db, organization_id=organizer.organization_id,
        )

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

        participant_ids = [p.user_id for p in meeting.participants if p.user_id != current_user.user_id]
        if data.status == "cancelled":
            self._notify_users(
                business_id, participant_ids, "Meeting cancelled",
                f"\"{meeting.title}\" has been cancelled.", meeting.id,
            )
            self._emit_event(
                EventType.MEETING_CANCELLED, business_id, meeting.id, current_user.user_id,
                description=f"Meeting cancelled: '{meeting.title}'",
            )
        else:
            self._notify_users(
                business_id, participant_ids, "Meeting updated",
                f"\"{meeting.title}\" has been updated.", meeting.id,
            )
            self._emit_event(
                EventType.MEETING_UPDATED, business_id, meeting.id, current_user.user_id,
                description=f"Meeting updated: '{meeting.title}'",
                data={"updated_fields": list(update_data.keys())},
            )

        cancelled = data.status == "cancelled"
        external_updates: list[tuple[MeetingExternalParticipant, str | None]] = []
        if meeting.external_participants:
            new_expires_at = meeting.end_time + timedelta(days=_RSVP_TOKEN_VALIDITY_DAYS_AFTER_MEETING)
            for ext in meeting.external_participants:
                raw_token = None
                if not cancelled:
                    # Mint a fresh token per update - the previous email's link
                    # stops working, matching this app's "raw token only ever
                    # exists in the email it was sent in" convention elsewhere
                    # (see UserInvitation) rather than reusing a static link.
                    raw_token = secrets.token_urlsafe(32)
                    ext.token_hash = _hash_token(raw_token)
                    ext.expires_at = new_expires_at
                external_updates.append((ext, raw_token))

        try:
            self.db.commit()
        except StaleDataError as e:
            self.db.rollback()
            raise ConcurrencyConflictError(
                "This meeting was changed by someone else - refresh and try again"
            ) from e
        self.db.refresh(meeting)

        for ext, raw_token in external_updates:
            try:
                if cancelled:
                    self._send_external_cancel_email(meeting, current_user, ext.email)
                else:
                    self._send_external_update_email(meeting, current_user, ext.email, raw_token)
            except Exception:
                logger.exception("Failed to send meeting %s email to %s", "cancellation" if cancelled else "update", ext.email)

        return meeting

    def _send_external_update_email(
        self, meeting: Meeting, organizer: CurrentUser, email: str, raw_token: str
    ) -> None:
        ics = build_meeting_ics(
            meeting_id=meeting.id, title=meeting.title, description=meeting.description,
            start_time=meeting.start_time, end_time=meeting.end_time,
            organizer_email=organizer.email, organizer_name=organizer.full_name,
            attendee_email=email, sequence=meeting.version, method="REQUEST",
        )
        accept_url, decline_url = self._rsvp_urls(raw_token)
        send_meeting_update_email(
            to_email=email, meeting_title=meeting.title, start_time_str=meeting.start_time.isoformat(),
            organizer_name=organizer.full_name, accept_url=accept_url, decline_url=decline_url,
            ics_bytes=ics, db=self.db, organization_id=organizer.organization_id,
        )

    def _send_external_cancel_email(self, meeting: Meeting, organizer: CurrentUser, email: str) -> None:
        ics = build_meeting_ics(
            meeting_id=meeting.id, title=meeting.title, description=meeting.description,
            start_time=meeting.start_time, end_time=meeting.end_time,
            organizer_email=organizer.email, organizer_name=organizer.full_name,
            attendee_email=email, sequence=meeting.version, method="CANCEL",
        )
        send_meeting_cancelled_email(
            to_email=email, meeting_title=meeting.title, start_time_str=meeting.start_time.isoformat(),
            organizer_name=organizer.full_name, ics_bytes=ics,
            db=self.db, organization_id=organizer.organization_id,
        )

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

        participant_ids = [p.user_id for p in meeting.participants if p.user_id != current_user.user_id]
        self._notify_users(
            business_id, participant_ids, "Call starting",
            f"{current_user.full_name} started the call for \"{meeting.title}\".", meeting.id,
        )
        self._emit_event(
            EventType.MEETING_STARTED, business_id, meeting.id, current_user.user_id,
            description=f"Meeting call started: '{meeting.title}'",
        )

        try:
            self.db.commit()
        except StaleDataError as e:
            self.db.rollback()
            raise ConcurrencyConflictError(
                "This meeting was changed by someone else - refresh and try again"
            ) from e
        self.db.refresh(meeting)
        return meeting

    def end_call(self, business_id: UUID, current_user: CurrentUser, meeting_id: UUID) -> Meeting | None:
        meeting = self.repo.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            return None
        if meeting.organizer_id != current_user.user_id:
            raise ValueError("Permission denied: Only the organizer can end this call")
        meeting.status = "completed"
        try:
            self.db.commit()
        except StaleDataError as e:
            self.db.rollback()
            raise ConcurrencyConflictError(
                "This meeting was changed by someone else - refresh and try again"
            ) from e
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

    # ── External (no-login) RSVP ─────────────────────────────────────────
    # Deliberately a separate code path from respond() above, not a reuse
    # of it - respond() is keyed on (meeting_id, current_user.user_id) and
    # this flow has no current_user at all; the token itself is the
    # credential, exactly like InvitationService.validate_token.

    def get_external_participant_by_token(self, raw_token: str) -> MeetingExternalParticipant:
        """Raises ValueError if the token is invalid or expired."""
        participant = self.repo.get_external_participant_by_token_hash(_hash_token(raw_token))
        if not participant:
            raise ValueError("Invalid or expired meeting invite link")

        expires_at = participant.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ValueError("Invalid or expired meeting invite link")

        return participant

    def respond_external(self, raw_token: str, response_status: str) -> MeetingExternalParticipant:
        """Accept or decline an external meeting invite via its token. No auth required."""
        participant = self.get_external_participant_by_token(raw_token)
        participant.response_status = response_status
        participant.responded_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(participant)
        return participant
