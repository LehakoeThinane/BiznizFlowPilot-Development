"""Document library (business-wide listing) tests."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload):
        yield


class TestDocumentLibrary:
    def test_lists_documents_across_entities(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "a.pdf", b"a", "application/pdf")
        service.upload(owner_user.business_id, owner_user, "task", uuid4(), "b.pdf", b"b", "application/pdf")

        docs, total = service.list_library(owner_user.business_id, owner_user)
        assert total == 2
        assert {d.filename for d in docs} == {"a.pdf", "b.pdf"}

    def test_filters_by_entity_type(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "a.pdf", b"a", "application/pdf")
        service.upload(owner_user.business_id, owner_user, "task", uuid4(), "b.pdf", b"b", "application/pdf")

        docs, total = service.list_library(owner_user.business_id, owner_user, entity_type="lead")
        assert total == 1
        assert docs[0].filename == "a.pdf"

    def test_filters_by_filename_search(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "invoice_march.pdf", b"a", "application/pdf")
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "contract.pdf", b"b", "application/pdf")

        docs, total = service.list_library(owner_user.business_id, owner_user, search="invoice")
        assert total == 1
        assert docs[0].filename == "invoice_march.pdf"

    def test_pagination(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        for i in range(5):
            service.upload(owner_user.business_id, owner_user, "lead", uuid4(), f"f{i}.pdf", b"x", "application/pdf")

        docs, total = service.list_library(owner_user.business_id, owner_user, skip=0, limit=2)
        assert total == 5
        assert len(docs) == 2

    def test_scoped_to_business(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "a.pdf", b"a", "application/pdf")

        docs, total = service.list_library(uuid4(), owner_user)
        assert total == 0
        assert docs == []
