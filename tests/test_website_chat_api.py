"""API tests for the public MM Nexus website chat widget endpoints
(app/api/website_chat.py)."""

from __future__ import annotations

import pytest

from app.models.business import Business
from app.schemas.auth import CurrentUser


def _fake_engine(reply: str):
    class _Engine:
        @staticmethod
        def chat(messages, system_prompt):
            return type("R", (), {"reply": reply})()

    return _Engine()


@pytest.fixture(autouse=True)
def _configure_widget(monkeypatch, owner_business: Business, owner_user: CurrentUser):
    monkeypatch.setattr("app.api.website_chat.settings.mm_nexus_business_id", str(owner_business.id))
    monkeypatch.setattr("app.services.website_chat.settings.mm_nexus_business_id", str(owner_business.id))
    monkeypatch.setattr(
        "app.services.website_chat.settings.mm_nexus_chat_assignee_user_id", str(owner_user.user_id)
    )


class TestSendWidgetMessage:
    def test_404_when_not_configured(self, client, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.settings.mm_nexus_business_id", "")
        r = client.post("/api/v1/public/website-chat/messages", json={"text": "Hello"})
        assert r.status_code == 404

    def test_first_message_mints_session_token_and_gets_ai_reply(self, client, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("Hi! How can I help?"))

        r = client.post("/api/v1/public/website-chat/messages", json={"text": "Hello"})
        assert r.status_code == 200
        body = r.json()
        assert body["session_token"]
        assert len(body["messages"]) == 2
        assert body["messages"][0]["from"] == "visitor"
        assert body["messages"][1]["from"] == "ai"
        assert body["messages"][1]["content"] == "Hi! How can I help?"

    def test_reusing_session_token_continues_conversation(self, client, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("First reply"))
        first = client.post("/api/v1/public/website-chat/messages", json={"text": "First"}).json()
        token = first["session_token"]

        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("Second reply"))
        second = client.post(
            "/api/v1/public/website-chat/messages", json={"session_token": token, "text": "Second"}
        ).json()
        assert second["session_token"] == token

    def test_empty_text_rejected(self, client):
        r = client.post("/api/v1/public/website-chat/messages", json={"text": ""})
        assert r.status_code == 422


class TestPollWidgetMessages:
    def test_404_for_unknown_session(self, client):
        r = client.get("/api/v1/public/website-chat/messages", params={"session_token": "not-a-real-token"})
        assert r.status_code == 404

    def test_poll_returns_new_messages(self, client, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("AI reply"))
        sent = client.post("/api/v1/public/website-chat/messages", json={"text": "Hello"}).json()
        token = sent["session_token"]

        r = client.get("/api/v1/public/website-chat/messages", params={"session_token": token})
        assert r.status_code == 200
        assert len(r.json()["messages"]) == 2
