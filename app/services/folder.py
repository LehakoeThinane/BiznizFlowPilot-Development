"""Folder service - nested containers for documents not tied to a CRM record.

🧨 RBAC: Any authenticated business member can create/view folders (team
collaboration, same permissiveness as document upload/notes). Rename and
delete are restricted to the folder's creator or an owner/manager - same
shape as document delete/restrict.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import PRIVILEGED_ROLES
from app.models.folder import Folder
from app.repositories.document import DocumentRepository
from app.repositories.folder import FolderRepository
from app.schemas.auth import CurrentUser


class FolderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FolderRepository(db)
        self.document_repo = DocumentRepository(db)

    @staticmethod
    def _can_manage(folder: Folder, current_user: CurrentUser) -> bool:
        is_creator = folder.created_by is not None and str(folder.created_by) == str(current_user.user_id)
        return is_creator or current_user.role in PRIVILEGED_ROLES

    def create(
        self, business_id: UUID, current_user: CurrentUser, name: str, parent_folder_id: UUID | None = None
    ) -> Folder:
        if not name or not name.strip():
            raise ValueError("Folder name is required")
        if parent_folder_id is not None:
            parent = self.repo.get(business_id=business_id, entity_id=parent_folder_id)
            if not parent:
                raise ValueError("Parent folder not found")

        return self.repo.create(
            business_id=business_id, name=name.strip(), parent_folder_id=parent_folder_id,
            created_by=current_user.user_id,
        )

    def get(self, business_id: UUID, current_user: CurrentUser, folder_id: UUID) -> Folder | None:
        return self.repo.get(business_id=business_id, entity_id=folder_id)

    def list_children(self, business_id: UUID, current_user: CurrentUser, parent_folder_id: UUID | None = None) -> list[Folder]:
        return self.repo.list_children(business_id, parent_folder_id)

    def rename(self, business_id: UUID, current_user: CurrentUser, folder_id: UUID, name: str) -> Folder | None:
        folder = self.repo.get(business_id=business_id, entity_id=folder_id)
        if not folder:
            return None
        if not self._can_manage(folder, current_user):
            raise PermissionError("Only the folder's creator or an owner/manager can rename it")
        if not name or not name.strip():
            raise ValueError("Folder name is required")

        folder.name = name.strip()
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def delete(self, business_id: UUID, current_user: CurrentUser, folder_id: UUID) -> bool:
        folder = self.repo.get(business_id=business_id, entity_id=folder_id)
        if not folder:
            return False
        if not self._can_manage(folder, current_user):
            raise PermissionError("Only the folder's creator or an owner/manager can delete it")

        if self.repo.has_children(business_id, folder_id):
            raise ValueError("Folder has sub-folders - delete or move them first")

        if self.document_repo.has_any_for_entity(business_id, "folder", folder_id):
            raise ValueError("Folder has documents in it - delete or move them first")

        return self.repo.delete(business_id=business_id, entity_id=folder_id)
