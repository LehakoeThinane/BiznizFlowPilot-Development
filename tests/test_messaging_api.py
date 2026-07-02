"""API tests for direct (1:1) messaging between colleagues."""

from __future__ import annotations

from uuid import uuid4

from app.core.security import create_access_token
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


class TestCreateConversation:
    def test_creates_new_conversation(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(manager_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["other_user"]["id"] == str(manager_user.user_id)
        assert body["unread_count"] == 0
        assert body["last_message"] is None

    def test_repeated_call_returns_same_conversation(
        self, client, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        headers = _auth_headers(owner_user)
        first = client.post(
            "/api/v1/messaging/conversations", json={"user_id": str(manager_user.user_id)}, headers=headers
        ).json()
        second = client.post(
            "/api/v1/messaging/conversations", json={"user_id": str(manager_user.user_id)}, headers=headers
        ).json()
        assert first["id"] == second["id"]

    def test_rejects_user_from_another_business(self, client, owner_user: CurrentUser, other_user: CurrentUser):
        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(other_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 404

    def test_rejects_self(self, client, owner_user: CurrentUser):
        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(owner_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400

    def test_requires_auth(self, client, manager_user: CurrentUser):
        r = client.post("/api/v1/messaging/conversations", json={"user_id": str(manager_user.user_id)})
        assert r.status_code == 401


class TestMessaging:
    def _create_conversation(self, client, owner_user: CurrentUser, manager_user: CurrentUser) -> str:
        r = client.post(
            "/api/v1/messaging/conversations",
            json={"user_id": str(manager_user.user_id)},
            headers=_auth_headers(owner_user),
        )
        return r.json()["id"]

    def test_send_and_list_messages(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        conversation_id = self._create_conversation(client, owner_user, manager_user)

        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/messages",
            json={"content": "Hey, got a minute?"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        assert r.json()["content"] == "Hey, got a minute?"
        assert r.json()["sender_id"] == str(owner_user.user_id)

        r = client.get(
            f"/api/v1/messaging/conversations/{conversation_id}/messages",
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["content"] == "Hey, got a minute?"

    def test_unread_count_and_mark_read(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        conversation_id = self._create_conversation(client, owner_user, manager_user)
        client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/messages",
            json={"content": "Hello"},
            headers=_auth_headers(owner_user),
        )

        r = client.get("/api/v1/messaging/unread-count", headers=_auth_headers(manager_user))
        assert r.status_code == 200
        assert r.json()["unread_count"] == 1

        r = client.get("/api/v1/messaging/conversations", headers=_auth_headers(manager_user))
        conversation = next(c for c in r.json()["items"] if c["id"] == conversation_id)
        assert conversation["unread_count"] == 1

        mark = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/read", headers=_auth_headers(manager_user)
        )
        assert mark.status_code == 204

        r = client.get("/api/v1/messaging/unread-count", headers=_auth_headers(manager_user))
        assert r.json()["unread_count"] == 0

    def test_non_participant_cannot_read_or_send(
        self, client, owner_user: CurrentUser, manager_user: CurrentUser, staff_user: CurrentUser
    ):
        conversation_id = self._create_conversation(client, owner_user, manager_user)
        headers = _auth_headers(staff_user)

        r = client.get(f"/api/v1/messaging/conversations/{conversation_id}/messages", headers=headers)
        assert r.status_code == 403

        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/messages",
            json={"content": "sneaky"},
            headers=headers,
        )
        assert r.status_code == 403

    def test_messages_for_unknown_conversation_404(self, client, owner_user: CurrentUser):
        r = client.get(
            f"/api/v1/messaging/conversations/{uuid4()}/messages", headers=_auth_headers(owner_user)
        )
        assert r.status_code == 404
