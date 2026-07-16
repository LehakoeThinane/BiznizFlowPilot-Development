"""Document checkout/check-in and version-history tests."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.document_checkout import DocumentCheckoutService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document_checkout.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document_checkout.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _make_doc(test_db: Session, uploader: CurrentUser):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, "lead", uuid4(), "report.docx", b"v1 data", "application/msword",
    )


class TestCheckOut:
    def test_checkout_locks_document(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)

        checked_out = service.check_out(owner_user.business_id, owner_user, doc.id)
        assert checked_out.checked_out_by == owner_user.user_id
        assert checked_out.checked_out_at is not None

    def test_second_user_cannot_check_out_locked_document(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        with pytest.raises(ValueError, match="already checked out"):
            service.check_out(staff_user.business_id, staff_user, doc.id)

    def test_same_user_can_recheckout_own_lock(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        # Idempotent - re-checking out your own lock should not raise
        again = service.check_out(owner_user.business_id, owner_user, doc.id)
        assert again.checked_out_by == owner_user.user_id


class TestCancelCheckout:
    def test_holder_can_cancel(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        released = service.cancel_checkout(owner_user.business_id, owner_user, doc.id)
        assert released.checked_out_by is None

    def test_other_non_privileged_user_cannot_cancel(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        with pytest.raises(PermissionError):
            service.cancel_checkout(staff_user.business_id, staff_user, doc.id)

    def test_owner_can_override_someone_elses_checkout(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, staff_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(staff_user.business_id, staff_user, doc.id)

        released = service.cancel_checkout(owner_user.business_id, owner_user, doc.id)
        assert released.checked_out_by is None


class TestCheckIn:
    def test_checkin_requires_prior_checkout(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)

        with pytest.raises(ValueError, match="check it out first"):
            service.check_in(owner_user.business_id, owner_user, doc.id, "report.docx", b"v2 data", "application/msword")

    def test_checkin_updates_document_and_bumps_version(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        updated = service.check_in(
            owner_user.business_id, owner_user, doc.id, "report_v2.docx", b"v2 data", "application/msword",
        )
        assert updated.version == 2
        assert updated.filename == "report_v2.docx"
        assert updated.size_bytes == len(b"v2 data")
        assert updated.checked_out_by is None

    def test_checkin_archives_prior_version(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)
        service.check_in(owner_user.business_id, owner_user, doc.id, "report_v2.docx", b"v2 data", "application/msword")

        versions = service.list_versions(owner_user.business_id, owner_user, doc.id)
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].filename == "report.docx"

    def test_non_holder_non_privileged_cannot_check_in(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        with pytest.raises(PermissionError):
            service.check_in(staff_user.business_id, staff_user, doc.id, "hijacked.docx", b"bad", "application/msword")

    def test_checkin_rejects_disallowed_extension(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)

        with pytest.raises(ValueError, match="not allowed"):
            service.check_in(owner_user.business_id, owner_user, doc.id, "malware.exe", b"data", "application/octet-stream")

    def test_multiple_checkins_accumulate_version_history(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)

        service.check_out(owner_user.business_id, owner_user, doc.id)
        service.check_in(owner_user.business_id, owner_user, doc.id, "v2.docx", b"v2", "application/msword")
        service.check_out(owner_user.business_id, owner_user, doc.id)
        service.check_in(owner_user.business_id, owner_user, doc.id, "v3.docx", b"v3", "application/msword")

        versions = service.list_versions(owner_user.business_id, owner_user, doc.id)
        assert [v.version_number for v in versions] == [2, 1]


class TestVersionDownload:
    def test_can_download_a_prior_version(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        service.check_out(owner_user.business_id, owner_user, doc.id)
        service.check_in(owner_user.business_id, owner_user, doc.id, "v2.docx", b"v2", "application/msword")

        versions = service.list_versions(owner_user.business_id, owner_user, doc.id)
        url = service.get_version_download_url(owner_user.business_id, owner_user, doc.id, versions[0].id)
        assert url == "https://signed.example/url"

    def test_missing_version_returns_none(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentCheckoutService(test_db)
        assert service.get_version_download_url(owner_user.business_id, owner_user, doc.id, uuid4()) is None
