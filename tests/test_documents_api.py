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


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.document.object_storage.upload", return_value="fake/key.txt"), \
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
