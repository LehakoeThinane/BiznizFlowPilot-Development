"""Document duplicate/template tests - copy a document's content onto a
(possibly different) entity without re-uploading the file."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


def _fake_get(storage_key):
    return b"original bytes"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document.object_storage.get", side_effect=_fake_get):
        yield


def _make_doc(test_db: Session, uploader: CurrentUser, entity_type="lead", entity_id=None):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, entity_type, entity_id or uuid4(),
        "worksheet.pdf", b"original bytes", "application/pdf",
    )


class TestDuplicateDocument:
    def test_duplicate_onto_same_entity(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentService(test_db)

        copy = service.duplicate(staff_user.business_id, staff_user, doc.id, doc.entity_type, doc.entity_id)

        assert copy is not None
        assert copy.id != doc.id
        assert copy.storage_key != doc.storage_key
        assert copy.filename == doc.filename
        assert copy.content_type == doc.content_type
        assert copy.entity_type == doc.entity_type
        assert copy.entity_id == doc.entity_id

    def test_duplicate_onto_different_entity(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user, entity_type="lead")
        service = DocumentService(test_db)
        new_customer_id = uuid4()

        copy = service.duplicate(staff_user.business_id, staff_user, doc.id, "customer", new_customer_id)

        assert copy.entity_type == "customer"
        assert copy.entity_id == new_customer_id
        # Original untouched
        assert doc.entity_type == "lead"

    def test_custom_filename_override(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentService(test_db)

        copy = service.duplicate(
            staff_user.business_id, staff_user, doc.id, doc.entity_type, uuid4(), filename="renamed.pdf",
        )

        assert copy.filename == "renamed.pdf"

    def test_filename_defaults_to_source_filename(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentService(test_db)

        copy = service.duplicate(staff_user.business_id, staff_user, doc.id, doc.entity_type, uuid4())

        assert copy.filename == doc.filename

    def test_unknown_document_returns_none(self, test_db: Session, staff_user: CurrentUser):
        service = DocumentService(test_db)
        result = service.duplicate(staff_user.business_id, staff_user, uuid4(), "lead", uuid4())
        assert result is None

    def test_restricted_document_without_access_raises(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser,
    ):
        doc = _make_doc(test_db, owner_user)
        from app.services.document_access import DocumentAccessService

        DocumentAccessService(test_db).set_restricted(owner_user.business_id, owner_user, doc.id, True)
        service = DocumentService(test_db)

        with pytest.raises(PermissionError):
            service.duplicate(staff_user.business_id, staff_user, doc.id, doc.entity_type, uuid4())
