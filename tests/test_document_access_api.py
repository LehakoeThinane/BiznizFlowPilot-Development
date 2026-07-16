"""API-level tests for document restrict/access-request routes.

RBAC and access-gating logic itself is thoroughly covered at the service
layer in tests/test_document_access.py with correctly matched same-tenant
fixtures - these are routing/wiring smoke tests only.
"""

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
         patch("app.services.document.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _upload_a_document(client: TestClient, token: str) -> str:
    r = client.post(
        "/api/v1/documents",
        data={"entity_type": "lead", "entity_id": str(uuid4())},
        files={"file": ("contract.pdf", b"data", "application/pdf")},
        headers=auth(token),
    )
    return r.json()["id"]


class TestRestrictApi:
    def test_owner_can_restrict_own_upload(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)

        r = client.patch(f"/api/v1/documents/{doc_id}/restrict", json={"restricted": True}, headers=auth(token))
        assert r.status_code == 200
        assert r.json()["restricted"] is True

    def test_uploader_still_has_access_after_restricting(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        client.patch(f"/api/v1/documents/{doc_id}/restrict", json={"restricted": True}, headers=auth(token))

        r = client.get(f"/api/v1/documents/{doc_id}/download-url", headers=auth(token))
        assert r.status_code == 200

    def test_list_response_includes_restricted_and_has_access_fields(self, client: TestClient, token: str):
        entity_id = str(uuid4())
        client.post(
            "/api/v1/documents",
            data={"entity_type": "lead", "entity_id": entity_id},
            files={"file": ("a.pdf", b"data", "application/pdf")},
            headers=auth(token),
        )

        r = client.get(f"/api/v1/documents?entity_type=lead&entity_id={entity_id}", headers=auth(token))
        assert r.status_code == 200
        doc = r.json()["items"][0]
        assert doc["restricted"] is False
        assert doc["has_access"] is True

    def test_restrict_requires_auth(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        r = client.patch(f"/api/v1/documents/{doc_id}/restrict", json={"restricted": True})
        assert r.status_code == 401


class TestAccessRequestApi:
    def test_request_access_to_unrestricted_document_rejected(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        r = client.post(f"/api/v1/documents/{doc_id}/access-requests", headers=auth(token))
        assert r.status_code == 400

    def test_uploader_requesting_own_restricted_document_rejected(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        client.patch(f"/api/v1/documents/{doc_id}/restrict", json={"restricted": True}, headers=auth(token))

        r = client.post(f"/api/v1/documents/{doc_id}/access-requests", headers=auth(token))
        assert r.status_code == 400

    def test_list_requests_for_document(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        client.patch(f"/api/v1/documents/{doc_id}/restrict", json={"restricted": True}, headers=auth(token))

        r = client.get(f"/api/v1/documents/{doc_id}/access-requests", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_approve_requires_auth(self, client: TestClient):
        r = client.post(f"/api/v1/documents/access-requests/{uuid4()}/approve")
        assert r.status_code == 401

    def test_approve_missing_request_returns_404(self, client: TestClient, token: str):
        r = client.post(f"/api/v1/documents/access-requests/{uuid4()}/approve", headers=auth(token))
        assert r.status_code == 404
