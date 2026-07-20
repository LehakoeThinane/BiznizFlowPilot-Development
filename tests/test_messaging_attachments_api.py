"""API tests for the chat attachment menu: files, contacts, events, polls, stickers."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture(autouse=True)
def _no_real_r2_calls():
    with patch("app.services.message_attachments.object_storage.upload", return_value="fake/key.txt"), \
         patch("app.api.messaging.object_storage.presigned_download_url", return_value="https://signed.example/url"):
        yield


@pytest.fixture
def conversation_id(client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser) -> str:
    r = client.post(
        "/api/v1/messaging/conversations",
        json={"user_id": str(manager_user.user_id)},
        headers=_auth_headers(owner_user),
    )
    assert r.status_code == 201
    return r.json()["id"]


class TestAttachmentUpload:
    def test_upload_document(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/attachments",
            files={"file": ("contract.pdf", b"fake pdf bytes", "application/pdf")},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["message_type"] == "document"
        assert body["attachment"]["filename"] == "contract.pdf"
        assert body["attachment"]["kind"] == "document"
        assert body["attachment"]["download_url"] == "https://signed.example/url"

    def test_upload_image_with_caption(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/attachments",
            data={"caption": "check this out"},
            files={"file": ("photo.jpg", b"fake jpg bytes", "image/jpeg")},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["message_type"] == "image"
        assert body["content"] == "check this out"

    def test_rejects_disallowed_extension(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/attachments",
            files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400

    def test_non_participant_cannot_upload(
        self, client: TestClient, staff_user: CurrentUser, conversation_id: str,
    ):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/attachments",
            files={"file": ("f.pdf", b"data", "application/pdf")},
            headers=_auth_headers(staff_user),
        )
        assert r.status_code == 403

    def test_appears_in_message_list(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/attachments",
            files={"file": ("contract.pdf", b"fake pdf bytes", "application/pdf")},
            headers=_auth_headers(owner_user),
        )
        r = client.get(
            f"/api/v1/messaging/conversations/{conversation_id}/messages",
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["message_type"] == "document"
        assert items[0]["attachment"]["filename"] == "contract.pdf"


@pytest.fixture
def sample_customer_snapshot(sample_customer) -> dict:
    """Plain-dict snapshot of the ORM fixture's fields.

    tests/conftest.py's shared `test_db` session is closed by `override_get_db`
    after *every* HTTP call the `client` fixture makes (see its `finally:
    session.close()`), so any ORM object read lazily after the first request
    (e.g. `sample_customer.id` accessed inside a test body, by which point the
    `conversation_id` fixture has already made its own request) raises
    DetachedInstanceError. Reading the fields into a plain dict here forces
    that read to happen during fixture setup, while the session is still open.
    """
    return {"id": str(sample_customer.id), "name": sample_customer.name}


class TestContactShare:
    def test_share_contact(self, client: TestClient, owner_user: CurrentUser, sample_customer_snapshot: dict, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/contacts",
            json={"customer_id": sample_customer_snapshot["id"]},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["message_type"] == "contact"
        assert body["shared_customer"]["name"] == sample_customer_snapshot["name"]

    def test_unknown_customer_404s(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/contacts",
            json={"customer_id": str(uuid4())},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 404


class TestStickers:
    def test_send_valid_sticker(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/stickers",
            json={"sticker_key": "fire"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["message_type"] == "sticker"
        assert body["sticker_key"] == "fire"

    def test_rejects_unknown_sticker_key(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/stickers",
            json={"sticker_key": "not-a-real-sticker"},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 400


class TestPolls:
    def _create_poll(self, client: TestClient, owner_user: CurrentUser, conversation_id: str, allow_multiple: bool = False) -> dict:
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/polls",
            json={"question": "Lunch?", "options": ["Pizza", "Sushi", "Tacos"], "allow_multiple": allow_multiple},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        return r.json()

    def test_create_poll(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        body = self._create_poll(client, owner_user, conversation_id)
        assert body["message_type"] == "poll"
        assert body["poll"]["question"] == "Lunch?"
        assert len(body["poll"]["options"]) == 3
        assert body["poll"]["total_votes"] == 0

    def test_too_few_options_rejected(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/polls",
            json={"question": "Lunch?", "options": ["Pizza"], "allow_multiple": False},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422  # pydantic min_length=2 on options

    def test_single_choice_vote_and_tally(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        poll_msg = self._create_poll(client, owner_user, conversation_id)
        poll_id = poll_msg["poll"]["id"]
        option_id = poll_msg["poll"]["options"][0]["id"]

        r = client.post(
            f"/api/v1/messaging/polls/{poll_id}/vote",
            json={"option_ids": [option_id]},
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_votes"] == 1
        assert body["options"][0]["vote_count"] == 1
        assert body["my_vote_option_ids"] == [option_id]

        # Re-voting for a different option replaces the previous single-choice vote.
        other_option_id = poll_msg["poll"]["options"][1]["id"]
        r = client.post(
            f"/api/v1/messaging/polls/{poll_id}/vote",
            json={"option_ids": [other_option_id]},
            headers=_auth_headers(manager_user),
        )
        body = r.json()
        assert body["total_votes"] == 1
        assert body["my_vote_option_ids"] == [other_option_id]

    def test_multi_choice_rejects_single_choice_poll(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        poll_msg = self._create_poll(client, owner_user, conversation_id, allow_multiple=False)
        poll_id = poll_msg["poll"]["id"]
        option_ids = [o["id"] for o in poll_msg["poll"]["options"][:2]]

        r = client.post(
            f"/api/v1/messaging/polls/{poll_id}/vote",
            json={"option_ids": option_ids},
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 400

    def test_allow_multiple_accepts_several_options(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        poll_msg = self._create_poll(client, owner_user, conversation_id, allow_multiple=True)
        poll_id = poll_msg["poll"]["id"]
        option_ids = [o["id"] for o in poll_msg["poll"]["options"][:2]]

        r = client.post(
            f"/api/v1/messaging/polls/{poll_id}/vote",
            json={"option_ids": option_ids},
            headers=_auth_headers(manager_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_votes"] == 2
        assert set(body["my_vote_option_ids"]) == set(option_ids)


class TestEvents:
    def test_schedule_new_event(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/events/schedule",
            json={
                "title": "Sync up",
                "description": "Quick chat",
                "start_time": "2026-08-01T10:00:00Z",
                "end_time": "2026-08-01T10:30:00Z",
                "call_type": "video",
                "participant_user_ids": [],
            },
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["message_type"] == "event"
        assert body["shared_meeting"]["title"] == "Sync up"

        # The other conversation participant should have been auto-invited
        # even though participant_user_ids was empty.
        r2 = client.get("/api/v1/meetings", headers=_auth_headers(manager_user))
        assert r2.status_code == 200
        assert any(m["title"] == "Sync up" for m in r2.json()["items"])

    def test_share_existing_event(self, client: TestClient, owner_user: CurrentUser, manager_user: CurrentUser, conversation_id: str):
        meeting_resp = client.post(
            "/api/v1/meetings",
            json={
                "title": "Standup",
                "start_time": "2026-08-02T09:00:00Z",
                "end_time": "2026-08-02T09:15:00Z",
                "call_type": "voice",
                "participant_user_ids": [str(manager_user.user_id)],
            },
            headers=_auth_headers(owner_user),
        )
        assert meeting_resp.status_code == 201, meeting_resp.text
        meeting_id = meeting_resp.json()["id"]

        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/events/share",
            json={"meeting_id": meeting_id},
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 201, r.text
        assert r.json()["shared_meeting"]["id"] == meeting_id

    def test_invalid_time_range_rejected(self, client: TestClient, owner_user: CurrentUser, conversation_id: str):
        r = client.post(
            f"/api/v1/messaging/conversations/{conversation_id}/events/schedule",
            json={
                "title": "Backwards",
                "start_time": "2026-08-01T10:30:00Z",
                "end_time": "2026-08-01T10:00:00Z",
                "call_type": "video",
                "participant_user_ids": [],
            },
            headers=_auth_headers(owner_user),
        )
        assert r.status_code == 422
