"""Document access-request workflow tests - restrict, request, approve, deny."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.document_access import DocumentAccessService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _make_doc(test_db: Session, uploader: CurrentUser):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, "lead", uuid4(), "contract.pdf", b"data", "application/pdf",
    )


class TestSetRestricted:
    def test_uploader_can_restrict_own_document(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentAccessService(test_db)

        updated = service.set_restricted(staff_user.business_id, staff_user, doc.id, True)
        assert updated.restricted is True

    def test_non_uploader_non_privileged_cannot_restrict(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentAccessService(test_db)

        with pytest.raises(PermissionError):
            service.set_restricted(staff_user.business_id, staff_user, doc.id, True)


class TestAccessGating:
    def test_unrestricted_document_downloadable_by_anyone(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        doc_service = DocumentService(test_db)

        url = doc_service.get_download_url(staff_user.business_id, staff_user, doc.id)
        assert url == "https://signed.example/url"

    def test_restricted_document_blocks_download_without_access(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)

        doc_service = DocumentService(test_db)
        with pytest.raises(PermissionError):
            doc_service.get_download_url(staff_user.business_id, staff_user, doc.id)

    def test_uploader_always_has_access_even_when_restricted(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(staff_user.business_id, staff_user, doc.id, True)

        doc_service = DocumentService(test_db)
        url = doc_service.get_download_url(staff_user.business_id, staff_user, doc.id)
        assert url == "https://signed.example/url"

    def test_owner_always_has_access_even_when_restricted(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, staff_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(staff_user.business_id, staff_user, doc.id, True)

        doc_service = DocumentService(test_db)
        url = doc_service.get_download_url(owner_user.business_id, owner_user, doc.id)
        assert url == "https://signed.example/url"


class TestRequestAccess:
    def test_request_access_creates_pending_request(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)

        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)
        assert req.status == "pending"
        assert req.user_id == staff_user.user_id

    def test_request_access_notifies_owners_and_managers(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)

        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)

        notif = (
            test_db.query(Notification)
            .filter(Notification.related_id == req.id, Notification.user_id == owner_user.user_id)
            .first()
        )
        assert notif is not None

    def test_cannot_request_access_to_unrestricted_document(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)

        with pytest.raises(ValueError, match="not restricted"):
            access_service.request_access(staff_user.business_id, staff_user, doc.id)

    def test_uploader_cannot_request_access_to_own_document(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(staff_user.business_id, staff_user, doc.id, True)

        with pytest.raises(ValueError, match="already have access"):
            access_service.request_access(staff_user.business_id, staff_user, doc.id)


class TestApproveDenyAccess:
    def test_approval_grants_access(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)

        approved = access_service.approve(owner_user.business_id, owner_user, req.id)
        assert approved.status == "approved"

        doc_service = DocumentService(test_db)
        url = doc_service.get_download_url(staff_user.business_id, staff_user, doc.id)
        assert url == "https://signed.example/url"

    def test_denial_leaves_document_inaccessible(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)

        denied = access_service.deny(owner_user.business_id, owner_user, req.id)
        assert denied.status == "denied"

        doc_service = DocumentService(test_db)
        with pytest.raises(PermissionError):
            doc_service.get_download_url(staff_user.business_id, staff_user, doc.id)

    def test_staff_cannot_review_requests(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)

        with pytest.raises(PermissionError):
            access_service.approve(staff_user.business_id, staff_user, req.id)

    def test_review_notifies_requester(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)
        access_service.approve(owner_user.business_id, owner_user, req.id)

        notif = (
            test_db.query(Notification)
            .filter(Notification.related_id == req.id, Notification.user_id == staff_user.user_id)
            .first()
        )
        assert notif is not None

    def test_re_request_after_denial_resets_to_pending(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        req = access_service.request_access(staff_user.business_id, staff_user, doc.id)
        access_service.deny(owner_user.business_id, owner_user, req.id)

        re_req = access_service.request_access(staff_user.business_id, staff_user, doc.id)
        assert re_req.id == req.id
        assert re_req.status == "pending"


class TestListRequests:
    def test_owner_can_list_requests(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)
        access_service.request_access(staff_user.business_id, staff_user, doc.id)

        requests = access_service.list_requests(owner_user.business_id, owner_user, doc.id)
        assert len(requests) == 1

    def test_staff_cannot_list_requests(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        access_service = DocumentAccessService(test_db)
        access_service.set_restricted(owner_user.business_id, owner_user, doc.id, True)

        with pytest.raises(PermissionError):
            access_service.list_requests(staff_user.business_id, staff_user, doc.id)
