"""Unit tests for app/integrations/object_storage.py's R2 wrapper - in
particular, the existence check added to presigned_download_url()/get() so a
storage key deleted directly in the R2 dashboard (outside the app) surfaces
as a clean, catchable error instead of a presigned URL that 404s when the
browser actually opens it."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.integrations import object_storage
from app.integrations.object_storage import ObjectNotFoundError, ObjectStorageError


def _not_found_error(operation_name: str) -> ClientError:
    return ClientError({"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}, operation_name)


def _other_error(operation_name: str) -> ClientError:
    return ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, operation_name)


class TestPresignedDownloadUrl:
    def test_raises_not_found_when_object_missing(self):
        fake_client = MagicMock()
        fake_client.head_object.side_effect = _not_found_error("HeadObject")
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            with pytest.raises(ObjectNotFoundError):
                object_storage.presigned_download_url("some/key.pdf", "key.pdf")
        fake_client.generate_presigned_url.assert_not_called()

    def test_returns_url_when_object_exists(self):
        fake_client = MagicMock()
        fake_client.head_object.return_value = {}
        fake_client.generate_presigned_url.return_value = "https://signed.example/url"
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            url = object_storage.presigned_download_url("some/key.pdf", "key.pdf")
        assert url == "https://signed.example/url"

    def test_other_client_errors_are_generic_storage_errors(self):
        fake_client = MagicMock()
        fake_client.head_object.side_effect = _other_error("HeadObject")
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            with pytest.raises(ObjectStorageError) as exc_info:
                object_storage.presigned_download_url("some/key.pdf", "key.pdf")
        assert not isinstance(exc_info.value, ObjectNotFoundError)

    def test_defaults_to_inline_disposition(self):
        """Clicking a document to look at it shouldn't force a save-to-disk
        dialog - inline is the default so browsers open/view PDFs, images,
        etc. directly. Callers with genuine download intent (external
        share/portal links) opt into disposition="attachment" explicitly."""
        fake_client = MagicMock()
        fake_client.head_object.return_value = {}
        fake_client.generate_presigned_url.return_value = "https://signed.example/url"
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            object_storage.presigned_download_url("some/key.pdf", "report.pdf")
        params = fake_client.generate_presigned_url.call_args.kwargs["Params"]
        assert params["ResponseContentDisposition"] == 'inline; filename="report.pdf"'

    def test_attachment_disposition_can_be_requested_explicitly(self):
        fake_client = MagicMock()
        fake_client.head_object.return_value = {}
        fake_client.generate_presigned_url.return_value = "https://signed.example/url"
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            object_storage.presigned_download_url("some/key.pdf", "report.pdf", disposition="attachment")
        params = fake_client.generate_presigned_url.call_args.kwargs["Params"]
        assert params["ResponseContentDisposition"] == 'attachment; filename="report.pdf"'


class TestGet:
    def test_raises_not_found_when_object_missing(self):
        fake_client = MagicMock()
        fake_client.get_object.side_effect = _not_found_error("GetObject")
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            with pytest.raises(ObjectNotFoundError):
                object_storage.get("some/key.pdf")

    def test_returns_bytes_when_object_exists(self):
        fake_body = MagicMock()
        fake_body.read.return_value = b"real content"
        fake_client = MagicMock()
        fake_client.get_object.return_value = {"Body": fake_body}
        with patch("app.integrations.object_storage._client", return_value=fake_client):
            assert object_storage.get("some/key.pdf") == b"real content"
