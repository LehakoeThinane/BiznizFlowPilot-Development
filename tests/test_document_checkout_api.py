"""API-level smoke tests for document checkout/checkin/version routes."""

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
         patch("app.services.document_checkout.object_storage.upload", return_value="fake/key2.txt"), \
         patch("app.services.document_checkout.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


def _upload_a_document(client: TestClient, token: str) -> str:
    r = client.post(
        "/api/v1/documents",
        data={"entity_type": "lead", "entity_id": str(uuid4())},
        files={"file": ("report.docx", b"v1", "application/msword")},
        headers=auth(token),
    )
    return r.json()["id"]


class TestCheckoutApi:
    def test_checkout_then_checkin_bumps_version(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)

        r = client.post(f"/api/v1/documents/{doc_id}/checkout", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["checked_out_by"] is not None

        r = client.post(
            f"/api/v1/documents/{doc_id}/checkin",
            files={"file": ("report_v2.docx", b"v2", "application/msword")},
            headers=auth(token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 2
        assert body["checked_out_by"] is None

    def test_checkin_without_checkout_rejected(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        r = client.post(
            f"/api/v1/documents/{doc_id}/checkin",
            files={"file": ("report_v2.docx", b"v2", "application/msword")},
            headers=auth(token),
        )
        assert r.status_code == 400

    def test_list_versions_after_checkin(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        client.post(f"/api/v1/documents/{doc_id}/checkout", headers=auth(token))
        client.post(
            f"/api/v1/documents/{doc_id}/checkin",
            files={"file": ("report_v2.docx", b"v2", "application/msword")},
            headers=auth(token),
        )

        r = client.get(f"/api/v1/documents/{doc_id}/versions", headers=auth(token))
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_cancel_checkout(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        client.post(f"/api/v1/documents/{doc_id}/checkout", headers=auth(token))

        r = client.post(f"/api/v1/documents/{doc_id}/checkout/cancel", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["checked_out_by"] is None

    def test_checkout_requires_auth(self, client: TestClient, token: str):
        doc_id = _upload_a_document(client, token)
        r = client.post(f"/api/v1/documents/{doc_id}/checkout")
        assert r.status_code == 401
