"""API-level tests for /api/v1/leads routes (CRUD + RBAC)."""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


# ── list + create ─────────────────────────────────────────────────────────────

class TestLeadListCreate:
    def test_list_leads_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/leads", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_create_lead_as_owner(self, client: TestClient, token: str):
        r = client.post(
            "/api/v1/leads",
            json={"status": "new", "source": "web_form"},
            headers=auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "new"
        assert data["source"] == "web_form"

    def test_create_lead_defaults(self, client: TestClient, token: str):
        r = client.post("/api/v1/leads", json={}, headers=auth(token))
        assert r.status_code == 200
        assert r.json()["id"] is not None

    def test_list_leads_after_create(self, client: TestClient, token: str):
        client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        r = client.get("/api/v1/leads", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_list_leads_filter_by_status(self, client: TestClient, token: str):
        client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        client.post("/api/v1/leads", json={"status": "contacted"}, headers=auth(token))
        r = client.get("/api/v1/leads?status=new", headers=auth(token))
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["status"] == "new" for i in items)

    def test_create_lead_requires_auth(self, client: TestClient):
        r = client.post("/api/v1/leads", json={"status": "new"})
        assert r.status_code in (401, 403)


# ── get by id ─────────────────────────────────────────────────────────────────

class TestLeadGet:
    def test_get_existing_lead(self, client: TestClient, token: str):
        create = client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        lead_id = create.json()["id"]
        r = client.get(f"/api/v1/leads/{lead_id}", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == lead_id

    def test_get_nonexistent_lead_returns_404(self, client: TestClient, token: str):
        r = client.get(f"/api/v1/leads/{uuid4()}", headers=auth(token))
        assert r.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────

class TestLeadUpdate:
    def test_update_lead_status(self, client: TestClient, token: str):
        create = client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        lead_id = create.json()["id"]
        r = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"status": "contacted"},
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "contacted"

    def test_update_invalid_transition_returns_403(self, client: TestClient, token: str):
        create = client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        lead_id = create.json()["id"]
        r = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"status": "won"},  # new → won is invalid
            headers=auth(token),
        )
        assert r.status_code == 403

    def test_update_nonexistent_lead_returns_404(self, client: TestClient, token: str):
        r = client.patch(
            f"/api/v1/leads/{uuid4()}",
            json={"status": "contacted"},
            headers=auth(token),
        )
        assert r.status_code == 404


# ── assign ────────────────────────────────────────────────────────────────────

class TestLeadAssign:
    def test_assign_lead(self, client: TestClient, token: str):
        create = client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        lead_id = create.json()["id"]
        user_id = str(uuid4())
        r = client.post(
            f"/api/v1/leads/{lead_id}/assign/{user_id}",
            headers=auth(token),
        )
        assert r.status_code == 200
        assert r.json()["assigned_to"] == user_id

    def test_assign_nonexistent_lead_returns_404(self, client: TestClient, token: str):
        r = client.post(
            f"/api/v1/leads/{uuid4()}/assign/{uuid4()}",
            headers=auth(token),
        )
        assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

class TestLeadDelete:
    def test_delete_lead_as_owner(self, client: TestClient, token: str):
        create = client.post("/api/v1/leads", json={"status": "new"}, headers=auth(token))
        lead_id = create.json()["id"]
        r = client.delete(f"/api/v1/leads/{lead_id}", headers=auth(token))
        assert r.status_code == 200
        assert "deleted" in r.json()["message"].lower()

    def test_delete_nonexistent_lead_returns_404(self, client: TestClient, token: str):
        r = client.delete(f"/api/v1/leads/{uuid4()}", headers=auth(token))
        assert r.status_code == 404
