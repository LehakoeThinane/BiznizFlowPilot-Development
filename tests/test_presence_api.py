"""API tests for user presence/status (online/away/busy/in_meeting/custom)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import CurrentUser


def _auth_headers(user: CurrentUser) -> dict[str, str]:
    token = create_access_token(
        {
            "user_id": str(user.user_id),
            "business_id": str(user.business_id),
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
        }
    )
    return {"Authorization": f"Bearer {token}"}


class TestUpdateStatus:
    def test_sets_each_preset(self, client, owner_user: CurrentUser):
        for preset in ("online", "away", "busy", "in_meeting"):
            r = client.patch(
                "/api/v1/users/me/status",
                json={"status": preset},
                headers=_auth_headers(owner_user),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == preset
            assert body["status_text"] is None
            assert body["is_online"] is True

    def test_custom_status_requires_text(self, client, owner_user: CurrentUser):
        r = client.patch(
            "/api/v1/users/me/status",
            json={"status": "custom"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422

        r = client.patch(
            "/api/v1/users/me/status",
            json={"status": "custom", "status_text": "   "},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422

    def test_sets_custom_status(self, client, owner_user: CurrentUser):
        r = client.patch(
            "/api/v1/users/me/status",
            json={"status": "custom", "status_text": "Out of office, may not respond"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "custom"
        assert body["status_text"] == "Out of office, may not respond"

    def test_switching_back_to_preset_clears_custom_text(self, client, owner_user: CurrentUser):
        headers = _auth_headers(owner_user)
        client.patch(
            "/api/v1/users/me/status",
            json={"status": "custom", "status_text": "Out sick"},
            headers=headers,
        )
        r = client.patch("/api/v1/users/me/status", json={"status": "away"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["status_text"] is None

    def test_rejects_invalid_status(self, client, owner_user: CurrentUser):
        r = client.patch(
            "/api/v1/users/me/status",
            json={"status": "on_vacation"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422

    def test_bumps_last_seen_at(self, client, owner_user: CurrentUser):
        r = client.patch(
            "/api/v1/users/me/status",
            json={"status": "busy"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 200
        assert r.json()["last_seen_at"] is not None

    def test_requires_auth(self, client):
        r = client.patch("/api/v1/users/me/status", json={"status": "away"})
        assert r.status_code == 401


class TestHeartbeat:
    def test_bumps_last_seen_at(self, client, owner_user: CurrentUser, test_db: Session):
        r = client.post("/api/v1/users/me/heartbeat", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        user = test_db.query(User).filter(User.id == owner_user.user_id).first()
        assert user.last_seen_at is not None

    def test_requires_auth(self, client):
        r = client.post("/api/v1/users/me/heartbeat")
        assert r.status_code == 401


class TestPresenceStaleness:
    def _backdate(self, test_db: Session, user_id, seconds: int) -> None:
        user = test_db.query(User).filter(User.id == user_id).first()
        user.status = "busy"
        user.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        test_db.commit()

    def test_stale_user_reports_offline_in_user_list(
        self, client, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        self._backdate(test_db, manager_user.user_id, seconds=200)

        r = client.get("/api/v1/users", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        by_id = {item["id"]: item for item in r.json()["items"]}
        manager_item = by_id[str(manager_user.user_id)]
        assert manager_item["presence"]["status"] == "offline"
        assert manager_item["presence"]["is_online"] is False

    def test_fresh_heartbeat_reports_stored_status_in_user_list(
        self, client, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        self._backdate(test_db, manager_user.user_id, seconds=10)

        r = client.get("/api/v1/users", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        by_id = {item["id"]: item for item in r.json()["items"]}
        manager_item = by_id[str(manager_user.user_id)]
        assert manager_item["presence"]["status"] == "busy"
        assert manager_item["presence"]["is_online"] is True

    def test_stale_user_reports_offline_in_conversation_summary(
        self, client, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        self._backdate(test_db, manager_user.user_id, seconds=200)

        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(manager_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        assert r.json()["other_user"]["presence"]["status"] == "offline"

    def test_active_user_reports_stored_status_in_conversation_summary(
        self, client, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        self._backdate(test_db, manager_user.user_id, seconds=10)

        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(manager_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        assert r.json()["other_user"]["presence"]["status"] == "busy"
