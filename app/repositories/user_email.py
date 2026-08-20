"""UserEmailAccount repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user_email import UserEmailAccount
from app.repositories.base import BaseRepository


class UserEmailAccountRepository(BaseRepository[UserEmailAccount]):
    """UserEmailAccount repository with business_id filtering."""

    def __init__(self, db: Session):
        super().__init__(db, UserEmailAccount)

    def get_by_user_id(self, business_id: UUID, user_id: UUID) -> UserEmailAccount | None:
        return (
            self.db.query(UserEmailAccount)
            .filter(UserEmailAccount.business_id == business_id, UserEmailAccount.user_id == user_id)
            .first()
        )

    def list_all_connected(self) -> list[UserEmailAccount]:
        """Every account with IMAP fully configured, across every business.

        🧨 Deliberately cross-tenant - only for the scheduled reply-watcher
        task, mirrors LeadGenScheduleRepository.list_all_active.
        """
        return (
            self.db.query(UserEmailAccount)
            .filter(
                UserEmailAccount.imap_host.isnot(None),
                UserEmailAccount.imap_username.isnot(None),
                UserEmailAccount.imap_password_encrypted.isnot(None),
            )
            .all()
        )
