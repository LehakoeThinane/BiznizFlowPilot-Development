"""Messaging service - direct (1:1) chat between colleagues."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.messaging import Conversation, Message
from app.models.poll import Poll
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.meeting import MeetingRepository
from app.repositories.messaging import ConversationRepository
from app.repositories.poll import PollRepository
from app.schemas.auth import CurrentUser
from app.schemas.meeting import MeetingCreate
from app.schemas.messaging import ConversationSummary, LastMessagePreview, OtherUser
from app.services.meeting import MeetingService

# Curated built-in sticker set - keys must match frontend/lib/stickers.ts exactly,
# since the server validates against this list rather than trusting arbitrary strings.
STICKER_KEYS = {
    "smile", "laugh", "heart", "thumbs_up", "thumbs_down", "fire", "clap", "party",
    "wave", "thinking", "cry", "angry", "cool", "wink", "star", "check", "cross",
    "hundred", "pray", "muscle", "eyes", "rocket", "clown", "ghost",
}

_TYPE_PREVIEW = {
    "document": "📄 Document",
    "image": "📷 Photo",
    "video": "🎥 Video",
    "audio": "🎤 Audio",
    "contact": "👤 Contact",
    "poll": "📊 Poll",
    "event": "📅 Event",
    "sticker": "Sticker",
}


def _preview_text(message: Message) -> str:
    """A conversation-list preview string for the last message - falls back
    to a type label when there's no caption (e.g. a bare photo or sticker)."""
    if message.content:
        return message.content
    return _TYPE_PREVIEW.get(message.message_type, "")


class MessagingService:
    """Direct-message service.

    🧨 RBAC: Any active user in a business can message any other active user
    in that same business — no role gate, matching open internal messaging.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ConversationRepository(db)
        self.polls = PollRepository(db)
        self.customers = CustomerRepository(db)
        self.meetings = MeetingRepository(db)

    def get_or_create_direct_conversation(self, business_id: UUID, current_user: CurrentUser, other_user_id: UUID) -> Conversation:
        if other_user_id == current_user.user_id:
            raise ValueError("Cannot start a conversation with yourself")

        other = (
            self.db.query(User)
            .filter(User.id == other_user_id, User.business_id == business_id, User.is_active.is_(True))
            .first()
        )
        if not other:
            raise LookupError("User not found")

        existing = self.repo.find_direct_conversation(business_id, current_user.user_id, other_user_id)
        if existing:
            return existing

        conversation = self.repo.create(business_id=business_id)
        self.repo.add_participant(conversation.id, current_user.user_id)
        self.repo.add_participant(conversation.id, other_user_id)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def summarize(self, conversation: Conversation, current_user_id: UUID) -> ConversationSummary:
        other_participant = next((p for p in conversation.participants if p.user_id != current_user_id), None)
        my_participant = next((p for p in conversation.participants if p.user_id == current_user_id), None)

        other_user = other_participant.user if other_participant else None
        last = self.repo.latest_message(conversation.id)
        unread = self.repo.unread_count_for_conversation(
            conversation.id, current_user_id, my_participant.last_read_at if my_participant else None,
        )
        return ConversationSummary(
            id=conversation.id,
            other_user=OtherUser(
                id=other_user.id if other_user else current_user_id,
                full_name=other_user.full_name if other_user else "Unknown",
                email=other_user.email if other_user else "",
            ),
            last_message=LastMessagePreview(
                content=_preview_text(last), created_at=last.created_at, sender_id=last.sender_id,
            ) if last else None,
            unread_count=unread,
        )

    def list_conversations(self, business_id: UUID, current_user: CurrentUser) -> list[ConversationSummary]:
        conversations = self.repo.list_for_user(business_id, current_user.user_id)
        summaries = [self.summarize(c, current_user.user_id) for c in conversations]
        summaries.sort(
            key=lambda s: s.last_message.created_at if s.last_message else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return summaries

    def _require_participant(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID) -> Conversation:
        conversation = self.repo.get(business_id=business_id, entity_id=conversation_id)
        if not conversation:
            raise LookupError("Conversation not found")
        if not self.repo.get_participant(conversation_id, current_user.user_id):
            raise ValueError("Permission denied: You are not part of this conversation")
        return conversation

    def list_messages(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, since: datetime | None = None, limit: int = 50) -> list[Message]:
        self._require_participant(business_id, current_user, conversation_id)
        return self.repo.list_messages(conversation_id, since=since, limit=limit)

    def send_message(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, content: str) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        message = self.repo.add_message(conversation_id, current_user.user_id, content)
        self.db.commit()
        self.db.refresh(message)
        return message

    def mark_read(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID) -> None:
        self._require_participant(business_id, current_user, conversation_id)
        self.repo.mark_read(conversation_id, current_user.user_id, datetime.now(timezone.utc))
        self.db.commit()

    def unread_count(self, business_id: UUID, current_user: CurrentUser) -> int:
        return self.repo.total_unread_count(business_id, current_user.user_id)

    # ── Contact sharing ──────────────────────────────────────────────────

    def share_contact(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, customer_id: UUID, caption: str | None = None) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        customer = self.customers.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            raise LookupError("Customer not found")
        message = self.repo.add_typed_message(conversation_id, current_user.user_id, "contact", content=caption, shared_customer_id=customer.id)
        self.db.commit()
        self.db.refresh(message)
        return message

    # ── Event sharing / scheduling ───────────────────────────────────────

    def share_meeting(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, meeting_id: UUID, caption: str | None = None) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        meeting = self.meetings.get(business_id=business_id, entity_id=meeting_id)
        if not meeting:
            raise LookupError("Meeting not found")
        is_organizer = meeting.organizer_id == current_user.user_id
        is_invitee = any(p.user_id == current_user.user_id for p in meeting.participants)
        if not is_organizer and not is_invitee:
            raise ValueError("Permission denied: You are not part of this meeting")
        message = self.repo.add_typed_message(conversation_id, current_user.user_id, "event", content=caption, shared_meeting_id=meeting.id)
        self.db.commit()
        self.db.refresh(message)
        return message

    def schedule_and_share_meeting(
        self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID,
        title: str, description: str | None, start_time: datetime, end_time: datetime,
        call_type: str, participant_user_ids: list[UUID],
    ) -> Message:
        """Create a new Meeting (via MeetingService, so invite notifications and
        event-timeline logging happen exactly as they do from the calendar page)
        and immediately share it as an event-type message in this conversation.

        The other conversation participant(s) are always included as invitees,
        even if the caller didn't list them explicitly.
        """
        conversation = self._require_participant(business_id, current_user, conversation_id)
        other_ids = {p.user_id for p in conversation.participants if p.user_id != current_user.user_id}
        full_participant_ids = list({*participant_user_ids, *other_ids}) or list(other_ids)

        meeting_data = MeetingCreate(
            title=title, description=description, start_time=start_time, end_time=end_time,
            call_type=call_type, participant_user_ids=full_participant_ids,
        )
        meeting = MeetingService(self.db).create(business_id, current_user, meeting_data)
        message = self.repo.add_typed_message(conversation_id, current_user.user_id, "event", shared_meeting_id=meeting.id)
        self.db.commit()
        self.db.refresh(message)
        return message

    # ── Stickers ──────────────────────────────────────────────────────────

    def send_sticker(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, sticker_key: str) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        if sticker_key not in STICKER_KEYS:
            raise ValueError("Unknown sticker")
        message = self.repo.add_typed_message(conversation_id, current_user.user_id, "sticker", sticker_key=sticker_key)
        self.db.commit()
        self.db.refresh(message)
        return message

    # ── Polls ─────────────────────────────────────────────────────────────

    def create_poll(self, business_id: UUID, current_user: CurrentUser, conversation_id: UUID, question: str, options: list[str], allow_multiple: bool) -> Message:
        self._require_participant(business_id, current_user, conversation_id)
        if len(options) < 2:
            raise ValueError("A poll needs at least 2 options")
        if len(options) > 10:
            raise ValueError("A poll can have at most 10 options")

        poll = self.polls.create(business_id=business_id, commit=False, conversation_id=conversation_id, created_by=current_user.user_id, question=question, allow_multiple=allow_multiple)
        for position, text in enumerate(options):
            self.polls.add_option(poll.id, text, position)
        self.db.flush()

        message = self.repo.add_typed_message(conversation_id, current_user.user_id, "poll", poll_id=poll.id)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _require_poll(self, business_id: UUID, current_user: CurrentUser, poll_id: UUID) -> Poll:
        poll = self.polls.get(business_id=business_id, entity_id=poll_id)
        if not poll:
            raise LookupError("Poll not found")
        self._require_participant(business_id, current_user, poll.conversation_id)
        return poll

    def cast_vote(self, business_id: UUID, current_user: CurrentUser, poll_id: UUID, option_ids: list[UUID]) -> Poll:
        poll = self._require_poll(business_id, current_user, poll_id)
        if not option_ids:
            raise ValueError("Select at least one option")
        if not poll.allow_multiple and len(option_ids) > 1:
            raise ValueError("This poll only allows a single choice")

        for option_id in option_ids:
            if not self.polls.get_option(poll.id, option_id):
                raise LookupError("Option not found")

        existing = self.polls.votes_for_user(poll.id, current_user.user_id)
        self.polls.remove_votes(existing)
        self.db.flush()
        for option_id in option_ids:
            self.polls.add_vote(poll.id, option_id, current_user.user_id)
        self.db.commit()
        self.db.refresh(poll)
        return poll

    def get_poll(self, business_id: UUID, current_user: CurrentUser, poll_id: UUID):
        return self._require_poll(business_id, current_user, poll_id)

    def poll_tally(self, poll_id: UUID) -> dict[UUID, int]:
        return self.polls.tally(poll_id)

    def my_poll_vote_option_ids(self, poll_id: UUID, user_id: UUID) -> list[UUID]:
        return [v.option_id for v in self.polls.votes_for_user(poll_id, user_id)]
