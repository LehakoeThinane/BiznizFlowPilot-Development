"""Folder service tests - create, nesting, rename, delete, RBAC, tenancy."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.folder import FolderService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload):
        yield


class TestFolderCreate:
    def test_creates_top_level_folder(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        folder = service.create(owner_user.business_id, owner_user, "BE HEARD Programme")

        assert folder.name == "BE HEARD Programme"
        assert folder.parent_folder_id is None
        assert folder.created_by == owner_user.user_id

    def test_creates_nested_folder(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        parent = service.create(owner_user.business_id, owner_user, "BE HEARD Programme")
        child = service.create(owner_user.business_id, owner_user, "One-on-one", parent.id)

        assert child.parent_folder_id == parent.id

    def test_rejects_blank_name(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        with pytest.raises(ValueError, match="required"):
            service.create(owner_user.business_id, owner_user, "   ")

    def test_rejects_missing_parent(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        with pytest.raises(ValueError, match="Parent folder not found"):
            service.create(owner_user.business_id, owner_user, "Orphan", uuid4())

    def test_staff_can_create_folders(self, test_db: Session, staff_user: CurrentUser):
        service = FolderService(test_db)
        folder = service.create(staff_user.business_id, staff_user, "Templates")
        assert folder.name == "Templates"


class TestFolderListing:
    def test_lists_top_level_folders(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        service.create(owner_user.business_id, owner_user, "A")
        service.create(owner_user.business_id, owner_user, "B")

        top_level = service.list_children(owner_user.business_id, owner_user)
        assert {f.name for f in top_level} == {"A", "B"}

    def test_lists_only_immediate_children(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        parent = service.create(owner_user.business_id, owner_user, "Parent")
        child = service.create(owner_user.business_id, owner_user, "Child", parent.id)
        service.create(owner_user.business_id, owner_user, "Grandchild", child.id)

        children_of_parent = service.list_children(owner_user.business_id, owner_user, parent.id)
        assert [f.name for f in children_of_parent] == ["Child"]

    def test_scoped_to_business(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        service.create(owner_user.business_id, owner_user, "Private")

        other_business_folders = service.list_children(uuid4(), owner_user)
        assert other_business_folders == []


class TestFolderRename:
    def test_creator_can_rename(self, test_db: Session, staff_user: CurrentUser):
        service = FolderService(test_db)
        folder = service.create(staff_user.business_id, staff_user, "Old Name")

        renamed = service.rename(staff_user.business_id, staff_user, folder.id, "New Name")
        assert renamed.name == "New Name"

    def test_non_creator_non_privileged_cannot_rename(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = FolderService(test_db)
        folder = service.create(owner_user.business_id, owner_user, "Owner's Folder")

        with pytest.raises(PermissionError):
            service.rename(staff_user.business_id, staff_user, folder.id, "Hijacked")

    def test_owner_can_rename_anyones_folder(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = FolderService(test_db)
        folder = service.create(staff_user.business_id, staff_user, "Staff Folder")

        renamed = service.rename(owner_user.business_id, owner_user, folder.id, "Renamed by Owner")
        assert renamed.name == "Renamed by Owner"


class TestFolderDelete:
    def test_deletes_empty_folder(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        folder = service.create(owner_user.business_id, owner_user, "Empty")

        assert service.delete(owner_user.business_id, owner_user, folder.id) is True

    def test_refuses_to_delete_folder_with_subfolders(self, test_db: Session, owner_user: CurrentUser):
        service = FolderService(test_db)
        parent = service.create(owner_user.business_id, owner_user, "Parent")
        service.create(owner_user.business_id, owner_user, "Child", parent.id)

        with pytest.raises(ValueError, match="sub-folders"):
            service.delete(owner_user.business_id, owner_user, parent.id)

    def test_refuses_to_delete_folder_with_documents(self, test_db: Session, owner_user: CurrentUser):
        folder_service = FolderService(test_db)
        folder = folder_service.create(owner_user.business_id, owner_user, "Has Files")

        doc_service = DocumentService(test_db)
        doc_service.upload(owner_user.business_id, owner_user, "folder", folder.id, "notes.txt", b"data", "text/plain")

        with pytest.raises(ValueError, match="documents"):
            folder_service.delete(owner_user.business_id, owner_user, folder.id)

    def test_non_creator_non_privileged_cannot_delete(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = FolderService(test_db)
        folder = service.create(owner_user.business_id, owner_user, "Owner's Folder")

        with pytest.raises(PermissionError):
            service.delete(staff_user.business_id, staff_user, folder.id)
