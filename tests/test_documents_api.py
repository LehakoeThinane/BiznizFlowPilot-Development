"""API-level tests for /api/v1/documents routes (upload, list, download, delete)."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


def _fake_upload(business_id, entity_type, entity_id, filename, content, content_type):
    return f"fake/{business_id}/{entity_type}/{entity_id}/{uuid4()}-{filename}"


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", side_effect=_fake_upload), \
         patch("app.services.document.object_storage.get", return_value=b"fake pdf bytes"), \
         patch("app.services.document.object_storage.presigned_download_url", return_value="https://signed.example/url"), \
         patch("app.services.document.object_storage.delete", return_value=None):
        yield


class TestDocumentUploadApi:
    def test_upload_via_multipart(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        r = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("contract.pdf", b"fake pdf bytes", "application/pdf")},
            headers=auth(token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["filename"] == "contract.pdf"
        assert body["entity_type"] == "lead"
        assert body["entity_id"] == lead_id

    def test_upload_requires_auth(self, client: TestClient):
        r = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": str(uuid4())},
            files={"file": ("f.pdf", b"data", "application/pdf")},
        )
        assert r.status_code == 401


class TestDocumentListApi:
    def test_list_returns_uploaded_documents(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("a.pdf", b"data", "application/pdf")},
            headers=auth(token),
        )

        r = client.get(f"/api/v1/documents?entity_type=lead&entity_id={lead_id}", headers=auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["filename"] == "a.pdf"


class TestDocumentDownloadApi:
    def test_returns_signed_url(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        upload = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("a.pdf", b"data", "application/pdf")},
            headers=auth(token),
        ).json()

        r = client.get(f"/api/v1/documents/{upload['id']}/download-url", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["url"] == "https://signed.example/url"

    def test_404_for_missing_document(self, client: TestClient, token: str):
        r = client.get(f"/api/v1/documents/{uuid4()}/download-url", headers=auth(token))
        assert r.status_code == 404

    def test_404_with_friendly_message_when_object_missing_from_storage(self, client: TestClient, token: str):
        """The R2 object was deleted independently of the app (e.g. by hand
        in the R2 dashboard) - the database row still exists, but the file
        behind it doesn't. This must surface as a clean 404, never a raw,
        unstyled R2 XML error page opened directly in the browser."""
        from app.integrations.object_storage import ObjectNotFoundError

        lead_id = str(uuid4())
        upload = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("a.pdf", b"data", "application/pdf")},
            headers=auth(token),
        ).json()

        with patch(
            "app.services.document.object_storage.presigned_download_url",
            side_effect=ObjectNotFoundError("Object not found: fake/key"),
        ):
            r = client.get(f"/api/v1/documents/{upload['id']}/download-url", headers=auth(token))
        assert r.status_code == 404
        assert "no longer available" in r.json()["detail"]


class TestDocumentContentApi:
    """The in-app editor reads content through this endpoint, not the
    download-url one - see DocumentContentResponse's docstring for why a
    presigned R2 URL doesn't work for this (R2 has no CORS policy allowing
    the app's own origin, so a browser fetch() to it is blocked outright)."""

    def test_returns_document_content(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        upload = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("a.html", b"<p>hello</p>", "text/html")},
            headers=auth(token),
        ).json()

        with patch("app.services.document.object_storage.get", return_value=b"<p>hello</p>"):
            r = client.get(f"/api/v1/documents/{upload['id']}/content", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["content"] == "<p>hello</p>"

    def test_404_for_missing_document(self, client: TestClient, token: str):
        r = client.get(f"/api/v1/documents/{uuid4()}/content", headers=auth(token))
        assert r.status_code == 404


class TestDocumentDuplicateApi:
    def test_duplicate_onto_different_entity(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        customer_id = str(uuid4())
        upload = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("worksheet.pdf", b"fake pdf bytes", "application/pdf")},
            headers=auth(token),
        ).json()

        r = client.post(
            f"/api/v1/documents/{upload['id']}/duplicate",
            json={"entity_type": "customer", "entity_id": customer_id},
            headers=auth(token),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["id"] != upload["id"]
        assert body["entity_type"] == "customer"
        assert body["entity_id"] == customer_id
        assert body["filename"] == "worksheet.pdf"

    def test_404_for_missing_document(self, client: TestClient, token: str):
        r = client.post(
            f"/api/v1/documents/{uuid4()}/duplicate",
            json={"entity_type": "lead", "entity_id": str(uuid4())},
            headers=auth(token),
        )
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient):
        r = client.post(
            f"/api/v1/documents/{uuid4()}/duplicate",
            json={"entity_type": "lead", "entity_id": str(uuid4())},
        )
        assert r.status_code == 401


class TestDocumentDeleteApi:
    def test_uploader_can_delete(self, client: TestClient, token: str):
        lead_id = str(uuid4())
        upload = client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": lead_id},
            files={"file": ("a.pdf", b"data", "application/pdf")},
            headers=auth(token),
        ).json()

        r = client.delete(f"/api/v1/documents/{upload['id']}", headers=auth(token))
        assert r.status_code == 204

    def test_404_for_missing_document(self, client: TestClient, token: str):
        r = client.delete(f"/api/v1/documents/{uuid4()}", headers=auth(token))
        assert r.status_code == 404
