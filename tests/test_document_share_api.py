"""API-level tests for document share-link routes, including the public redemption endpoint."""

from unittest.mock import patch

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
         patch("app.services.document_share.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _upload_a_document(client: TestClient, token: str) -> str:
    from uuid import uuid4
    r = client.post(
        "/api/v1/documents",
        data={"entity_type": "lead", "entity_id": str(uuid4())},
        files={"file": ("contract.pdf", b"data", "application/pdf")},
        headers=auth(token),
    )
    return r.json()["id"]


class TestShareLinkApi:
    def test_create_and_list_share_link(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)

        r = client.post(f"/api/v1/documents/{doc_id}/share", json={"expires_in_days": 3}, headers=auth(token))
        assert r.status_code == 201
        body = r.json()
        assert body["document_id"] == doc_id
        assert "/api/v1/share/" in body["url"]

        r = client.get(f"/api/v1/documents/{doc_id}/share", headers=auth(token))
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_revoke_share_link(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        link = client.post(f"/api/v1/documents/{doc_id}/share", json={}, headers=auth(token)).json()

        r = client.delete(f"/api/v1/documents/share/{link['id']}", headers=auth(token))
        assert r.status_code == 204

        r = client.get(f"/api/v1/documents/{doc_id}/share", headers=auth(token))
        assert r.json()["items"] == []

    def test_share_requires_auth(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        r = client.post(f"/api/v1/documents/{doc_id}/share", json={})
        assert r.status_code == 401


class TestPublicRedemptionApi:
    def test_valid_token_redirects_to_signed_url(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        link = client.post(f"/api/v1/documents/{doc_id}/share", json={}, headers=auth(token)).json()
        share_token = link["url"].rsplit("/", 1)[-1]

        r = client.get(f"/api/v1/share/{share_token}", follow_redirects=False)
        assert r.status_code == 307
        assert r.headers["location"] == "https://signed.example/url"

    def test_invalid_token_returns_404(self, client: TestClient):
        r = client.get("/api/v1/share/not-a-real-token")
        assert r.status_code == 404

    def test_redemption_requires_no_auth(self, client: TestClient, token: str):
        """The whole point of a share link is that it works with zero auth headers."""
        doc_id = _upload_a_document(client, token)
        link = client.post(f"/api/v1/documents/{doc_id}/share", json={}, headers=auth(token)).json()
        share_token = link["url"].rsplit("/", 1)[-1]

        r = client.get(f"/api/v1/share/{share_token}", follow_redirects=False)
        assert r.status_code == 307
