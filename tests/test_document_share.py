"""Document sharing tests - create/list/revoke external links, public redemption."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.document_share import MAX_EXPIRY_DAYS, DocumentShareService, _as_aware_utc


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document_share.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _make_doc(test_db: Session, uploader: CurrentUser):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, "lead", uuid4(), "contract.pdf", b"data", "application/pdf",
    )


class TestCreateShareLink:
    def test_uploader_can_create_link(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentShareService(test_db)

        link = service.create_link(staff_user.business_id, staff_user, doc.id)

        assert link is not None
        assert link.token
        assert _as_aware_utc(link.expires_at) > datetime.now(timezone.utc)

    def test_owner_can_create_link_for_someone_elses_document(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, staff_user)
        service = DocumentShareService(test_db)

        link = service.create_link(owner_user.business_id, owner_user, doc.id)
        assert link is not None

    def test_non_uploader_non_privileged_cannot_create_link(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)

        with pytest.raises(PermissionError):
            service.create_link(staff_user.business_id, staff_user, doc.id)

    def test_expiry_is_clamped_to_max(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)

        link = service.create_link(owner_user.business_id, owner_user, doc.id, expires_in_days=999)

        max_expected = datetime.now(timezone.utc) + timedelta(days=MAX_EXPIRY_DAYS)
        assert _as_aware_utc(link.expires_at) <= max_expected + timedelta(minutes=1)

    def test_missing_document_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentShareService(test_db)
        assert service.create_link(owner_user.business_id, owner_user, uuid4()) is None


class TestListAndRevokeShareLinks:
    def test_lists_only_active_links(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)
        link = service.create_link(owner_user.business_id, owner_user, doc.id)

        links = service.list_links(owner_user.business_id, owner_user, doc.id)
        assert len(links) == 1

        service.revoke_link(owner_user.business_id, owner_user, link.id)
        links_after_revoke = service.list_links(owner_user.business_id, owner_user, doc.id)
        assert links_after_revoke == []

    def test_non_uploader_non_privileged_cannot_revoke(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser
    ):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)
        link = service.create_link(owner_user.business_id, owner_user, doc.id)

        with pytest.raises(PermissionError):
            service.revoke_link(staff_user.business_id, staff_user, link.id)

    def test_revoke_missing_link_returns_false(self, test_db: Session, owner_user: CurrentUser):
        service = DocumentShareService(test_db)
        assert service.revoke_link(owner_user.business_id, owner_user, uuid4()) is False


class TestPublicRedemption:
    def test_valid_token_resolves_to_signed_url(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)
        link = service.create_link(owner_user.business_id, owner_user, doc.id)

        url = service.resolve_public_download(link.token)
        assert url == "https://signed.example/url"

    def test_unknown_token_returns_none(self, test_db: Session):
        service = DocumentShareService(test_db)
        assert service.resolve_public_download("not-a-real-token") is None

    def test_revoked_token_returns_none(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)
        link = service.create_link(owner_user.business_id, owner_user, doc.id)
        service.revoke_link(owner_user.business_id, owner_user, link.id)

        assert service.resolve_public_download(link.token) is None

    def test_expired_token_returns_none(self, test_db: Session, owner_user: CurrentUser):
        doc = _make_doc(test_db, owner_user)
        service = DocumentShareService(test_db)
        link = service.create_link(owner_user.business_id, owner_user, doc.id)

        link.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        test_db.commit()

        assert service.resolve_public_download(link.token) is None
