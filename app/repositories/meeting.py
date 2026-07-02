"""Meeting repository - data access layer."""

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.meeting import Meeting, MeetingParticipant
from app.repositories.base import BaseRepository


class MeetingRepository(BaseRepository[Meeting]):
    """Meeting repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, Meeting)

    def list_for_business(self, business_id: UUID, skip: int = 0, limit: int = 20) -> list[Meeting]:
        return (
            self.db.query(Meeting)
            .filter(Meeting.business_id == business_id)
            .order_by(Meeting.start_time.desc())
            .offset(skip).limit(limit).all()
        )

    def count_for_business(self, business_id: UUID) -> int:
        return self.db.query(Meeting).filter(Meeting.business_id == business_id).count()

    def list_for_participant(self, business_id: UUID, user_id: UUID, skip: int = 0, limit: int = 20) -> list[Meeting]:
        return (
            self.db.query(Meeting)
            .outerjoin(MeetingParticipant, MeetingParticipant.meeting_id == Meeting.id)
            .filter(
                Meeting.business_id == business_id,
                or_(Meeting.organizer_id == user_id, MeetingParticipant.user_id == user_id),
            )
            .distinct()
            .order_by(Meeting.start_time.desc())
            .offset(skip).limit(limit).all()
        )

    def count_for_participant(self, business_id: UUID, user_id: UUID) -> int:
        return (
            self.db.query(Meeting.id)
            .outerjoin(MeetingParticipant, MeetingParticipant.meeting_id == Meeting.id)
            .filter(
                Meeting.business_id == business_id,
                or_(Meeting.organizer_id == user_id, MeetingParticipant.user_id == user_id),
            )
            .distinct()
            .count()
        )

    def list_active_for_user(self, business_id: UUID, user_id: UUID) -> list[Meeting]:
        """Meetings currently in_progress that this user organizes or is invited to."""
        return (
            self.db.query(Meeting)
            .outerjoin(MeetingParticipant, MeetingParticipant.meeting_id == Meeting.id)
            .filter(
                Meeting.business_id == business_id,
                Meeting.status == "in_progress",
                or_(Meeting.organizer_id == user_id, MeetingParticipant.user_id == user_id),
            )
            .distinct()
            .all()
        )

    # ── Participants ─────────────────────────────────────────────────────

    def get_participant(self, meeting_id: UUID, user_id: UUID) -> MeetingParticipant | None:
        return (
            self.db.query(MeetingParticipant)
            .filter(MeetingParticipant.meeting_id == meeting_id, MeetingParticipant.user_id == user_id)
            .first()
        )

    def add_participant(self, meeting_id: UUID, user_id: UUID, response_status: str = "pending") -> MeetingParticipant:
        participant = MeetingParticipant(
            meeting_id=meeting_id, user_id=user_id, response_status=response_status,
        )
        self.db.add(participant)
        return participant
