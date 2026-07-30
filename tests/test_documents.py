"""Document service tests - upload, list, download URL, delete, RBAC, tenancy."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.integrations.object_storage import ObjectStorageError
from app.models.event import Event
from app.schemas.auth import CurrentUser
from app.services.document import MAX_UPLOAD_BYTES, DocumentService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    """Every test in this module stubs out real R2 network calls by default."""
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document.object_storage.delete", return_value=None):
        yield


class TestDocumentUpload:
    def test_upload_creates_document(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        lead_id = uuid4()

        doc = service.upload(
            owner_user.business_id, owner_user, "lead", lead_id,
            "contract.pdf", b"fake pdf bytes", "application/pdf",
        )

        assert doc.filename == "contract.pdf"
        assert doc.content_type == "application/pdf"
        assert doc.size_bytes == len(b"fake pdf bytes")
        assert doc.entity_type == "lead"
        assert doc.entity_id == lead_id
        assert doc.uploaded_by == owner_user.user_id

    def test_upload_emits_activity_event(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        lead_id = uuid4()

        service.upload(owner_user.business_id, owner_user, "lead", lead_id, "contract.pdf", b"data", "application/pdf")

        event = (
            test_db.query(Event)
            .filter(Event.entity_type == "lead", Event.entity_id == lead_id)
            .first()
        )
        assert event is not None
        assert "contract.pdf" in event.description

    def test_rejects_oversized_file(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        oversized = b"x" * (MAX_UPLOAD_BYTES + 1)

        with pytest.raises(ValueError, match="exceeds"):
            service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "big.zip", oversized, "application/zip")

    def test_rejects_empty_file(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)

        with pytest.raises(ValueError, match="empty"):
            service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "empty.txt", b"", "text/plain")

    def test_rejects_disallowed_extension(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)

        with pytest.raises(ValueError, match="not allowed"):
            service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "virus.exe", b"data", "application/octet-stream")

    def test_allows_expected_business_document_types(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        for filename in ["report.pdf", "sheet.xlsx", "photo.jpg", "notes.txt", "archive.zip"]:
            doc = service.upload(owner_user.business_id, owner_user, "lead", uuid4(), filename, b"data", "application/octet-stream")
            assert doc.filename == filename

    def test_storage_failure_propagates(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        with patch("app.services.document.object_storage.upload", side_effect=ObjectStorageError("boom")):
            with pytest.raises(ObjectStorageError):
                service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "f.pdf", b"data", "application/pdf")


class TestDocumentList:
    def test_lists_documents_for_entity(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        lead_id = uuid4()
        service.upload(owner_user.business_id, owner_user, "lead", lead_id, "a.pdf", b"a", "application/pdf")
        service.upload(owner_user.business_id, owner_user, "lead", lead_id, "b.pdf", b"b", "application/pdf")
        service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "other.pdf", b"c", "application/pdf")

        docs = service.list_by_entity(owner_user.business_id, owner_user, "lead", lead_id)

        assert len(docs) == 2
        assert {d.filename for d in docs} == {"a.pdf", "b.pdf"}


class TestDocumentDownload:
    def test_returns_presigned_url(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        doc = service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "f.pdf", b"data", "application/pdf")

        with patch("app.services.document.object_storage.presigned_download_url", return_value="https://signed.example/url"):
            url = service.get_download_url(owner_user.business_id, owner_user, doc.id)

        assert url == "https://signed.example/url"

    def test_returns_none_for_missing_document(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        assert service.get_download_url(owner_user.business_id, owner_user, uuid4()) is None


class TestDocumentGetContent:
    """The in-app editor reads content through get_content(), not a
    presigned URL - see DocumentContentResponse's docstring: R2 has no CORS
    policy allowing the app's own origin, so a browser-side fetch() to a
    presigned URL is blocked outright. Routing bytes through our own API
    avoids depending on R2 CORS configuration entirely."""

    def test_returns_document_content_as_text(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        doc = service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "f.html", b"<p>hello</p>", "text/html")

        with patch("app.services.document.object_storage.get", return_value=b"<p>hello</p>"):
            content = service.get_content(owner_user.business_id, owner_user, doc.id)

        assert content == "<p>hello</p>"

    def test_returns_none_for_missing_document(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        assert service.get_content(owner_user.business_id, owner_user, uuid4()) is None


class TestDocumentDelete:
    def test_uploader_can_delete_own_document(self, test_db: Session, staff_user: CurrentUser):
        service = DocumentService(test_db)
        doc = service.upload(staff_user.business_id, staff_user, "lead", uuid4(), "f.pdf", b"data", "application/pdf")

        assert service.delete(staff_user.business_id, staff_user, doc.id) is True

    def test_non_uploader_non_privileged_cannot_delete(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = DocumentService(test_db)
        doc = service.upload(owner_user.business_id, owner_user, "lead", uuid4(), "f.pdf", b"data", "application/pdf")

        with pytest.raises(PermissionError):
            service.delete(staff_user.business_id, staff_user, doc.id)

    def test_owner_can_delete_someone_elses_document(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        service = DocumentService(test_db)
        doc = service.upload(staff_user.business_id, staff_user, "lead", uuid4(), "f.pdf", b"data", "application/pdf")

        assert service.delete(owner_user.business_id, owner_user, doc.id) is True


class TestDocumentMultiTenancy:
    def test_document_not_visible_from_another_business(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentService(test_db)
        lead_id = uuid4()
        service.upload(owner_user.business_id, owner_user, "lead", lead_id, "secret.pdf", b"data", "application/pdf")

        docs = service.list_by_entity(uuid4(), owner_user, "lead", lead_id)
        assert docs == []
