"""API-level smoke tests for folder routes."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


class TestFolderApi:
    def test_create_and_list_folder(self, client: TestClient, token: str):
        r = client.post("/api/v1/folders", json={"name": "BE HEARD Programme"}, headers=auth(token))
        assert r.status_code == 201
        folder_id = r.json()["id"]

        r = client.get("/api/v1/folders", headers=auth(token))
        assert r.status_code == 200
        assert any(f["id"] == folder_id for f in r.json()["items"])

    def test_create_nested_folder_and_list_children(self, client: TestClient, token: str):
        parent = client.post("/api/v1/folders", json={"name": "Programme"}, headers=auth(token)).json()
        client.post(
            "/api/v1/folders",
            json={"name": "One-on-one", "parent_folder_id": parent["id"]},
            headers=auth(token),
        )

        r = client.get(f"/api/v1/folders?parent_folder_id={parent['id']}", headers=auth(token))
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    def test_rename_folder(self, client: TestClient, token: str):
        folder = client.post("/api/v1/folders", json={"name": "Old"}, headers=auth(token)).json()
        r = client.patch(f"/api/v1/folders/{folder['id']}", json={"name": "New"}, headers=auth(token))
        assert r.status_code == 200
        assert r.json()["name"] == "New"

    def test_delete_empty_folder(self, client: TestClient, token: str):
        folder = client.post("/api/v1/folders", json={"name": "Temp"}, headers=auth(token)).json()
        r = client.delete(f"/api/v1/folders/{folder['id']}", headers=auth(token))
        assert r.status_code == 204

    def test_create_requires_auth(self, client: TestClient):
        r = client.post("/api/v1/folders", json={"name": "X"})
        assert r.status_code == 401

    def test_get_missing_folder_returns_404(self, client: TestClient, token: str):
        r = client.get(f"/api/v1/folders/{uuid4()}", headers=auth(token))
        assert r.status_code == 404
