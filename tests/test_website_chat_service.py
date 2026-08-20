"""Tests for app/services/website_chat.py - the AI-first, human-takeover
logic behind the MM Nexus website chat widget."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.messaging import Conversation
from app.schemas.auth import CurrentUser
from app.services import website_chat
from app.services.messaging import MessagingService
from app.services.website_chat import WebsiteChatNotConfiguredError


@pytest.fixture(autouse=True)
def _configure_widget(monkeypatch, owner_business: Business, owner_user: CurrentUser):
    monkeypatch.setattr("app.services.website_chat.settings.mm_nexus_business_id", str(owner_business.id))
    monkeypatch.setattr(
        "app.services.website_chat.settings.mm_nexus_chat_assignee_user_id", str(owner_user.user_id)
    )


def _fake_engine(reply: str):
    class _Engine:
        @staticmethod
        def chat(messages, system_prompt):
            return type("R", (), {"reply": reply})()

    return _Engine()


class TestNotConfigured:
    def test_raises_when_unconfigured(self, test_db: Session, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.settings.mm_nexus_business_id", "")
        with pytest.raises(WebsiteChatNotConfiguredError):
            website_chat.send_visitor_message(test_db, None, "Hello")


class TestSendVisitorMessage:
    def test_first_message_creates_session_and_gets_ai_reply(self, test_db: Session, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("Hi there!"))

        token, messages = website_chat.send_visitor_message(test_db, None, "Hello, what do you do?")

        assert token
        assert len(messages) == 2
        assert messages[0].content == "Hello, what do you do?"
        assert messages[0].is_ai_reply is False
        assert messages[1].content == "Hi there!"
        assert messages[1].is_ai_reply is True

    def test_reusing_token_continues_same_conversation(self, test_db: Session, monkeypatch):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("First reply"))
        token, first_messages = website_chat.send_visitor_message(test_db, None, "First question")
        conversation_id = first_messages[0].conversation_id

        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("Second reply"))
        token2, second_messages = website_chat.send_visitor_message(test_db, token, "Second question")

        assert token2 == token
        assert second_messages[0].conversation_id == conversation_id

    def test_engine_failure_falls_back_gracefully(self, test_db: Session, monkeypatch):
        class _BrokenEngine:
            @staticmethod
            def chat(messages, system_prompt):
                raise RuntimeError("boom")

        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _BrokenEngine())

        token, messages = website_chat.send_visitor_message(test_db, None, "Hello")
        assert len(messages) == 2
        assert "AI error" in messages[1].content
        assert messages[1].is_ai_reply is True

    def test_no_ai_reply_once_staff_has_taken_over(self, test_db: Session, monkeypatch, owner_user: CurrentUser):
        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("First reply"))
        token, first_messages = website_chat.send_visitor_message(test_db, None, "First question")
        conversation_id = first_messages[0].conversation_id

        # The real takeover mechanism: an ordinary authenticated staff reply
        # through the existing messaging service, see app/services/messaging.py.
        MessagingService(test_db).send_message(
            owner_user.business_id, owner_user, conversation_id, "Hi, I'm a real person now"
        )

        conversation = test_db.get(Conversation, conversation_id)
        assert conversation.ai_active is False

        monkeypatch.setattr("app.services.website_chat.get_engine", lambda: _fake_engine("Should not appear"))
        _, second_messages = website_chat.send_visitor_message(test_db, token, "Are you still there?")

        assert len(second_messages) == 1
        assert second_messages[0].content == "Are you still there?"
