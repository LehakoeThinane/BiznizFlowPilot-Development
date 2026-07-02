"""UserInvitation repository."""

from typing import Optional
from uuid import UUID

from app.models.user_invitation import UserInvitation
from app.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[UserInvitation]):
    """Invitation repository (business-scoped, plus an org-wide read for IT Admins)."""

    def __init__(self, db):
        """Initialize with UserInvitation model."""
        super().__init__(db, UserInvitation)

    def get_by_token_hash(self, token_hash: str) -> Optional[UserInvitation]:
        """Look up an invitation by its hashed token (no business_id filter - token is the credential)."""
        return (
            self.db.query(UserInvitation)
            .filter(UserInvitation.token_hash == token_hash)
            .first()
        )

    def get_pending_for_business_email(self, business_id: UUID, email: str) -> Optional[UserInvitation]:
        """Find an existing pending invite for this business+email, if any."""
        return (
            self.db.query(UserInvitation)
            .filter(
                UserInvitation.business_id == business_id,
                UserInvitation.email == email,
                UserInvitation.status == "pending",
            )
            .first()
        )

    def list_for_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[UserInvitation]:
        """List invitations across every subsidiary in an organization (IT Admin cross-subsidiary view).

        🧨 Deliberately bypasses the single-business_id filter - this is the
        one sanctioned exception documented alongside get_org_admin.
        """
        return (
            self.db.query(UserInvitation)
            .filter(UserInvitation.organization_id == organization_id)
            .order_by(UserInvitation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
