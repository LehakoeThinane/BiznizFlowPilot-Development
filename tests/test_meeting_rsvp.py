"""API tests for the public (no-login) meeting RSVP endpoints."""

from __future__ import annotations

import re
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


def _extract_token(url: str) -> str:
    match = re.search(r"/meeting-rsvp/([^?]+)", url)
    assert match, f"no token found in {url!r}"
    return match.group(1)


def _create_meeting_with_external_invite(client, owner_user: CurrentUser, monkeypatch, email="guest@external.com") -> str:
    """Creates a meeting with one external invitee and returns the raw RSVP token."""
    captured = {}
    monkeypatch.setattr(
        "app.services.meeting.send_meeting_invite_email",
        lambda **kwargs: captured.update(accept_url=kwargs["accept_url"]),
    )
    start = datetime.now(timezone.utc) + timedelta(days=1)
    r = client.post(
        "/api/v1/meetings",
        json={
            "title": "Client Call",
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
            "call_type": "video",
            "participant_user_ids": [],
            "external_emails": [email],
        },
        headers=_auth_headers(owner_user),
    )
    assert r.status_code == 201
    return _extract_token(captured["accept_url"])


class TestMeetingRsvp:
    def test_get_details_no_auth_required(self, client, owner_user: CurrentUser, monkeypatch):
        token = _create_meeting_with_external_invite(client, owner_user, monkeypatch)
        r = client.get(f"/api/v1/meeting-rsvp/{token}")  # deliberately no Authorization header
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "Client Call"
        assert body["response_status"] == "pending"

    def test_accept_via_token(self, client, owner_user: CurrentUser, monkeypatch):
        token = _create_meeting_with_external_invite(client, owner_user, monkeypatch)
        r = client.post(f"/api/v1/meeting-rsvp/{token}/respond", json={"response_status": "accepted"})
        assert r.status_code == 200
        assert r.json()["response_status"] == "accepted"

        # Reflected back on the meeting itself.
        r2 = client.get(f"/api/v1/meeting-rsvp/{token}")
        assert r2.json()["response_status"] == "accepted"

    def test_decline_via_token(self, client, owner_user: CurrentUser, monkeypatch):
        token = _create_meeting_with_external_invite(client, owner_user, monkeypatch)
        r = client.post(f"/api/v1/meeting-rsvp/{token}/respond", json={"response_status": "declined"})
        assert r.status_code == 200
        assert r.json()["response_status"] == "declined"

    def test_invalid_token_404(self, client):
        r = client.get("/api/v1/meeting-rsvp/not-a-real-token")
        assert r.status_code == 404

    def test_invalid_token_respond_404(self, client):
        r = client.post("/api/v1/meeting-rsvp/not-a-real-token/respond", json={"response_status": "accepted"})
        assert r.status_code == 404

    def test_expired_token_404(self, client, owner_user: CurrentUser, monkeypatch, test_db):
        from app.models.meeting import MeetingExternalParticipant

        token = _create_meeting_with_external_invite(client, owner_user, monkeypatch)
        from app.services.meeting import _hash_token

        participant = (
            test_db.query(MeetingExternalParticipant)
            .filter(MeetingExternalParticipant.token_hash == _hash_token(token))
            .first()
        )
        participant.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        test_db.commit()

        r = client.get(f"/api/v1/meeting-rsvp/{token}")
        assert r.status_code == 404

    def test_response_visible_on_meeting_detail_to_organizer(self, client, owner_user: CurrentUser, monkeypatch):
        token = _create_meeting_with_external_invite(client, owner_user, monkeypatch)
        client.post(f"/api/v1/meeting-rsvp/{token}/respond", json={"response_status": "accepted"})

        r = client.get("/api/v1/meetings", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        meeting = next(m for m in r.json()["items"] if m["title"] == "Client Call")
        ext = next(e for e in meeting["external_participants"] if e["email"] == "guest@external.com")
        assert ext["response_status"] == "accepted"
