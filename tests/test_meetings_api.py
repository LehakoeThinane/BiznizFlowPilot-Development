"""API tests for meeting scheduling and Agora call endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _meeting_body(participant_id, **overrides) -> dict:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    body = {
        "title": "Sprint Planning",
        "description": "Weekly sync",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=30)).isoformat(),
        "call_type": "video",
        "participant_user_ids": [str(participant_id)],
    }
    body.update(overrides)
    return body


class TestCreateMeeting:
    def test_organizer_schedules_meeting(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        r = client.post(
            "/api/v1/meetings",
            json=_meeting_body(manager_user.user_id),
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["title"] == "Sprint Planning"
        assert body["organizer_id"] == str(owner_user.user_id)
        assert body["status"] == "scheduled"
        participant_ids = {p["user_id"] for p in body["participants"]}
        assert participant_ids == {str(owner_user.user_id), str(manager_user.user_id)}
        organizer_participant = next(p for p in body["participants"] if p["user_id"] == str(owner_user.user_id))
        assert organizer_participant["response_status"] == "accepted"
        invitee_participant = next(p for p in body["participants"] if p["user_id"] == str(manager_user.user_id))
        assert invitee_participant["response_status"] == "pending"

    def test_rejects_participant_from_another_business(self, client, owner_user: CurrentUser, other_user: CurrentUser):
        r = client.post(
            "/api/v1/meetings",
            json=_meeting_body(other_user.user_id),
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400

    def test_rejects_end_before_start(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        start = datetime.now(timezone.utc) + timedelta(days=1)
        r = client.post(
            "/api/v1/meetings",
            json=_meeting_body(
                manager_user.user_id,
                start_time=start.isoformat(),
                end_time=(start - timedelta(minutes=30)).isoformat(),
            ),
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422

    def test_requires_auth(self, client, manager_user: CurrentUser):
        r = client.post("/api/v1/meetings", json=_meeting_body(manager_user.user_id))
        assert r.status_code == 401


class TestMeetingLifecycle:
    def _create(self, client, owner_user: CurrentUser, manager_user: CurrentUser) -> dict:
        r = client.post(
            "/api/v1/meetings",
            json=_meeting_body(manager_user.user_id),
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201
        return r.json()

    def test_list_includes_meetings_for_organizer_and_invitee(
        self, client, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        self._create(client, owner_user, manager_user)

        r = client.get("/api/v1/meetings", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

        r = client.get("/api/v1/meetings", headers=_auth_headers(manager_user))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_invitee_can_accept(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        meeting = self._create(client, owner_user, manager_user)

        r = client.post(
            f"/api/v1/meetings/{meeting['id']}/respond",
            json={"response_status": "accepted"},
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 200
        invitee = next(p for p in r.json()["participants"] if p["user_id"] == str(manager_user.user_id))
        assert invitee["response_status"] == "accepted"

    def test_non_participant_cannot_respond(
        self, client, owner_user: CurrentUser, manager_user: CurrentUser, staff_user: CurrentUser
    ):
        meeting = self._create(client, owner_user, manager_user)
        r = client.post(
            f"/api/v1/meetings/{meeting['id']}/respond",
            json={"response_status": "accepted"},
            headers=_auth_headers(staff_user),
        )
        assert r.status_code == 403

    def test_only_organizer_can_start_call(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        meeting = self._create(client, owner_user, manager_user)

        r = client.post(f"/api/v1/meetings/{meeting['id']}/start", headers=_auth_headers(manager_user))
        assert r.status_code == 403

        r = client.post(f"/api/v1/meetings/{meeting['id']}/start", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_active_meetings_surfaced_to_invitee(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        meeting = self._create(client, owner_user, manager_user)
        client.post(f"/api/v1/meetings/{meeting['id']}/start", headers=_auth_headers(owner_user))

        r = client.get("/api/v1/meetings/active", headers=_auth_headers(manager_user))
        assert r.status_code == 200
        assert any(m["id"] == meeting["id"] for m in r.json())

    def test_join_without_agora_configured_returns_503(
        self, client, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        meeting = self._create(client, owner_user, manager_user)
        r = client.post(f"/api/v1/meetings/{meeting['id']}/join", headers=_auth_headers(owner_user))
        assert r.status_code == 503

    def test_only_organizer_can_end_call(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        meeting = self._create(client, owner_user, manager_user)
        client.post(f"/api/v1/meetings/{meeting['id']}/start", headers=_auth_headers(owner_user))

        r = client.post(f"/api/v1/meetings/{meeting['id']}/end", headers=_auth_headers(manager_user))
        assert r.status_code == 403

        r = client.post(f"/api/v1/meetings/{meeting['id']}/end", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_only_organizer_can_cancel(self, client, owner_user: CurrentUser, manager_user: CurrentUser):
        meeting = self._create(client, owner_user, manager_user)

        r = client.patch(
            f"/api/v1/meetings/{meeting['id']}",
            json={"status": "cancelled"},
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 403

        r = client.patch(
            f"/api/v1/meetings/{meeting['id']}",
            json={"status": "cancelled"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_get_meeting_not_found(self, client, owner_user: CurrentUser):
        from uuid import uuid4

        r = client.get(f"/api/v1/meetings/{uuid4()}", headers=_auth_headers(owner_user))
        assert r.status_code == 404
