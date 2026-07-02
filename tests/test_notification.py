"""Notification API tests — list, count, mark read."""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def token(client: TestClient, registered_user: dict) -> str:
    return registered_user["access_token"]


def seed_notification(test_db: Session, business_id, user_id, is_read: bool = False) -> Notification:
    n = Notification(
        id=uuid4(),
        business_id=business_id,
        user_id=user_id,
        type="system",
        title="Test notification",
        message="This is a test.",
        is_read=is_read,
    )
    test_db.add(n)
    test_db.commit()
    return n


class TestNotificationList:
    def test_list_empty(self, client: TestClient, token: str):
        r = client.get("/api/v1/notifications", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["unread"] == 0
        assert data["items"] == []

    def test_notifications_after_employee_create(self, client: TestClient, token: str):
        """Creating an employee triggers a notification for managers/owners."""
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Notif", "last_name": "Test", "gross_salary": "20000"},
            headers=auth(token),
        )
        r = client.get("/api/v1/notifications", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        titles = [n["title"] for n in data["items"]]
        assert any("employee" in t.lower() for t in titles)

    def test_notifications_after_leave_request(self, client: TestClient, token: str):
        emp = client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Leave", "last_name": "Notif", "gross_salary": "15000"},
            headers=auth(token),
        ).json()
        client.post(
            "/api/v1/hr/leave-requests",
            json={
                "employee_id": emp["id"],
                "start_date": "2026-06-01",
                "end_date": "2026-06-03",
                "days_requested": "3",
            },
            headers=auth(token),
        )
        r = client.get("/api/v1/notifications", headers=auth(token))
        titles = [n["title"] for n in r.json()["items"]]
        assert any("leave" in t.lower() for t in titles)

    def test_unread_only_filter(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Filter", "last_name": "Test", "gross_salary": "20000"},
            headers=auth(token),
        )
        r = client.get("/api/v1/notifications?unread_only=true", headers=auth(token))
        assert r.status_code == 200
        assert all(not n["is_read"] for n in r.json()["items"])


class TestNotificationCount:
    def test_count_zero_initially(self, client: TestClient, token: str):
        r = client.get("/api/v1/notifications/count", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["unread"] == 0
        assert r.json()["total"] == 0

    def test_count_after_notification(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Count", "last_name": "Test", "gross_salary": "20000"},
            headers=auth(token),
        )
        r = client.get("/api/v1/notifications/count", headers=auth(token))
        assert r.json()["unread"] >= 1


class TestMarkRead:
    def test_mark_single_read(self, client: TestClient, token: str):
        client.post(
            "/api/v1/hr/employees",
            json={"first_name": "Mark", "last_name": "Read", "gross_salary": "20000"},
            headers=auth(token),
        )
        notifs = client.get("/api/v1/notifications", headers=auth(token)).json()["items"]
        assert len(notifs) > 0
        notif_id = notifs[0]["id"]

        r = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=auth(token))
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_mark_all_read(self, client: TestClient, token: str):
        for i in range(2):
            client.post(
                "/api/v1/hr/employees",
                json={"first_name": f"All{i}", "last_name": "Read", "gross_salary": "20000"},
                headers=auth(token),
            )
        r = client.patch("/api/v1/notifications/read-all", headers=auth(token))
        assert r.status_code == 204

        count = client.get("/api/v1/notifications/count", headers=auth(token)).json()
        assert count["unread"] == 0

    def test_mark_nonexistent_read(self, client: TestClient, token: str):
        r = client.patch(f"/api/v1/notifications/{uuid4()}/read", headers=auth(token))
        assert r.status_code == 404
