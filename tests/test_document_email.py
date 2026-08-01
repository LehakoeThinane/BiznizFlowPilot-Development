"""DocumentService.email_document tests - "email this document" from the
in-app editor/library, delivered through the caller's own connected
mailbox (UserEmailAccountService), not a separate delivery path."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.user_email import EmailAccountNotConfiguredError


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


def _fake_get(storage_key):
    return b"stored file bytes"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document.object_storage.get", side_effect=_fake_get):
        yield


def _make_doc(test_db: Session, uploader: CurrentUser, filename="report.pdf", content_type="application/pdf"):
    return DocumentService(test_db).upload(
        uploader.business_id, uploader, "lead", uuid4(), filename, b"stored file bytes", content_type,
    )


class TestEmailDocument:
    def test_unknown_document_returns_none(self, test_db: Session, staff_user: CurrentUser):
        service = DocumentService(test_db)
        result = service.email_document(
            staff_user.business_id, staff_user, uuid4(), "to@example.com", "Subject", "Body",
        )
        assert result is None

    def test_restricted_document_without_access_raises(
        self, test_db: Session, owner_user: CurrentUser, staff_user: CurrentUser,
    ):
        doc = _make_doc(test_db, owner_user)
        from app.services.document_access import DocumentAccessService

        DocumentAccessService(test_db).set_restricted(owner_user.business_id, owner_user, doc.id, True)
        service = DocumentService(test_db)

        with pytest.raises(PermissionError):
            service.email_document(staff_user.business_id, staff_user, doc.id, "to@example.com", "Subject", "Body")

    def test_raises_when_no_mailbox_connected(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user)
        service = DocumentService(test_db)

        with pytest.raises(EmailAccountNotConfiguredError):
            service.email_document(staff_user.business_id, staff_user, doc.id, "to@example.com", "Subject", "Body")

    def test_sends_stored_file_as_attachment_by_default(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user, filename="report.pdf", content_type="application/pdf")
        service = DocumentService(test_db)

        with patch("app.services.document.UserEmailAccountService.send_message") as mock_send:
            result = service.email_document(
                staff_user.business_id, staff_user, doc.id, "to@example.com", "Subject", "Body",
            )

        assert result is not None
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[:5] == (staff_user.business_id, staff_user.user_id, "to@example.com", "Subject", "Body")
        attachments = kwargs["attachments"]
        assert len(attachments) == 1
        assert attachments[0].filename == "report.pdf"
        assert attachments[0].content == b"stored file bytes"
        assert attachments[0].mime_type == "application/pdf"

    def test_live_content_html_overrides_stored_content(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user, filename="notes.html", content_type="text/html")
        service = DocumentService(test_db)

        with patch("app.services.document.UserEmailAccountService.send_message") as mock_send:
            service.email_document(
                staff_user.business_id, staff_user, doc.id, "to@example.com", "Subject", "Body",
                content_html="<p>unsaved edits</p>",
            )

        attachments = mock_send.call_args.kwargs["attachments"]
        assert attachments[0].content == b"<p>unsaved edits</p>"
        assert attachments[0].mime_type == "text/html"

    def test_live_content_html_is_sanitized(self, test_db: Session, staff_user: CurrentUser):
        doc = _make_doc(test_db, staff_user, filename="notes.html", content_type="text/html")
        service = DocumentService(test_db)

        with patch("app.services.document.UserEmailAccountService.send_message") as mock_send:
            service.email_document(
                staff_user.business_id, staff_user, doc.id, "to@example.com", "Subject", "Body",
                content_html="<p>hi</p><script>alert(1)</script>",
            )

        sent_bytes = mock_send.call_args.kwargs["attachments"][0].content
        assert b"<script>" not in sent_bytes
        assert b"<p>hi</p>" in sent_bytes
