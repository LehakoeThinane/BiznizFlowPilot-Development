"""Folder repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.folder import Folder
from app.repositories.base import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    """Folder repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, Folder)

    def list_children(self, business_id: UUID, parent_folder_id: UUID | None) -> list[Folder]:
        """List immediate sub-folders of a folder (or top-level folders when parent_folder_id is None).

        🧨 CRITICAL: Filters by business_id.
        """
        return (
            self.db.query(Folder)
            .filter(Folder.business_id == business_id, Folder.parent_folder_id == parent_folder_id)
            .order_by(Folder.name.asc())
            .all()
        )

    def has_children(self, business_id: UUID, folder_id: UUID) -> bool:
        return (
            self.db.query(Folder.id)
            .filter(Folder.business_id == business_id, Folder.parent_folder_id == folder_id)
            .first()
            is not None
        )
