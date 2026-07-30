"""Customer portal tests - durable, revocable external document access."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.auth import CurrentUser
from app.services.customer_portal import CustomerPortalService, _hash_token
from app.services.document import DocumentService
from app.services.document_access import DocumentAccessService


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.customer_portal.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _make_customer(test_db: Session, business_id) -> Customer:
    customer = Customer(id=uuid4(), business_id=business_id, name="Acme Client")
    test_db.add(customer)
    test_db.commit()
    return customer


def _make_doc_for_customer(test_db: Session, uploader: CurrentUser, customer_id):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, "customer", customer_id, "worksheet.pdf", b"data", "application/pdf",
    )


class TestGenerateOrRegenerate:
    def test_owner_can_generate(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)

        result = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert result is not None
        access, raw_token = result
        assert raw_token != access.token_hash
        assert access.token_hash == _hash_token(raw_token)

    def test_staff_cannot_generate(self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)

        with pytest.raises(PermissionError):
            service.generate_or_regenerate(staff_user.business_id, staff_user, customer.id)

    def test_regenerating_revokes_prior_token(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)

        _, first_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)
        _, second_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert service.resolve(first_token) is None
        assert service.resolve(second_token) is not None

    def test_unknown_customer_returns_none(self, test_db: Session, owner_user: CurrentUser):
        service = CustomerPortalService(test_db)
        assert service.generate_or_regenerate(owner_user.business_id, owner_user, uuid4()) is None


class TestRevoke:
    def test_revoke_with_no_active_access_is_a_noop(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)
        assert service.revoke(owner_user.business_id, owner_user, customer.id) is False

    def test_revoke_disables_the_token(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert service.revoke(owner_user.business_id, owner_user, customer.id) is True
        assert service.resolve(raw_token) is None


class TestResolveAndListDocuments:
    def test_resolve_unknown_token_returns_none(self, test_db: Session):
        assert CustomerPortalService(test_db).resolve("not-a-real-token") is None

    def test_resolve_bumps_last_accessed_at(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert service.resolve(raw_token) is not None
        access = service.repo.get_active_for_customer(customer.id)
        assert access.last_accessed_at is not None

    def test_list_documents_excludes_other_customers_documents(self, test_db: Session, owner_user: CurrentUser):
        customer_a = _make_customer(test_db, owner_user.business_id)
        customer_b = _make_customer(test_db, owner_user.business_id)
        _make_doc_for_customer(test_db, owner_user, customer_a.id)
        _make_doc_for_customer(test_db, owner_user, customer_b.id)

        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer_a.id)

        result = service.list_documents(raw_token)
        assert result is not None
        _, _, docs = result
        assert len(docs) == 1

    def test_list_documents_excludes_restricted_documents(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        doc = _make_doc_for_customer(test_db, owner_user, customer.id)
        DocumentAccessService(test_db).set_restricted(owner_user.business_id, owner_user, doc.id, True)

        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        result = service.list_documents(raw_token)
        assert result is not None
        _, _, docs = result
        assert docs == []


class TestGetDocumentDownloadUrl:
    def test_returns_none_for_another_customers_document(self, test_db: Session, owner_user: CurrentUser):
        customer_a = _make_customer(test_db, owner_user.business_id)
        customer_b = _make_customer(test_db, owner_user.business_id)
        other_doc = _make_doc_for_customer(test_db, owner_user, customer_b.id)

        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer_a.id)

        assert service.get_document_download_url(raw_token, other_doc.id) is None

    def test_returns_none_for_restricted_document(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        doc = _make_doc_for_customer(test_db, owner_user, customer.id)
        DocumentAccessService(test_db).set_restricted(owner_user.business_id, owner_user, doc.id, True)

        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert service.get_document_download_url(raw_token, doc.id) is None

    def test_returns_url_for_valid_document(self, test_db: Session, owner_user: CurrentUser):
        customer = _make_customer(test_db, owner_user.business_id)
        doc = _make_doc_for_customer(test_db, owner_user, customer.id)

        service = CustomerPortalService(test_db)
        _, raw_token = service.generate_or_regenerate(owner_user.business_id, owner_user, customer.id)

        assert service.get_document_download_url(raw_token, doc.id) == "https://signed.example/url"
