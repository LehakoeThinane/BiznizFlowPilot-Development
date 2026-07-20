"""Poll repository - data access layer for chat polls."""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.poll import Poll, PollOption, PollVote
from app.repositories.base import BaseRepository


class PollRepository(BaseRepository[Poll]):
    """Poll repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, Poll)

    def add_option(self, poll_id: UUID, text: str, position: int) -> PollOption:
        option = PollOption(poll_id=poll_id, text=text, position=position)
        self.db.add(option)
        return option

    def get_option(self, poll_id: UUID, option_id: UUID) -> PollOption | None:
        return (
            self.db.query(PollOption)
            .filter(PollOption.id == option_id, PollOption.poll_id == poll_id)
            .first()
        )

    def votes_for_user(self, poll_id: UUID, user_id: UUID) -> list[PollVote]:
        return (
            self.db.query(PollVote)
            .join(PollOption, PollOption.id == PollVote.option_id)
            .filter(PollOption.poll_id == poll_id, PollVote.user_id == user_id)
            .all()
        )

    def add_vote(self, poll_id: UUID, option_id: UUID, user_id: UUID) -> PollVote:
        vote = PollVote(poll_id=poll_id, option_id=option_id, user_id=user_id)
        self.db.add(vote)
        return vote

    def remove_votes(self, votes: list[PollVote]) -> None:
        for vote in votes:
            self.db.delete(vote)

    def tally(self, poll_id: UUID) -> dict[UUID, int]:
        rows = (
            self.db.query(PollVote.option_id, func.count(PollVote.id))
            .filter(PollVote.poll_id == poll_id)
            .group_by(PollVote.option_id)
            .all()
        )
        return {option_id: count for option_id, count in rows}
