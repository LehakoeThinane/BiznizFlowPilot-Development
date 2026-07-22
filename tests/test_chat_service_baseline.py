"""Baseline coverage for the pre-existing (previously untested) chat send
flow, using the echo engine (no external calls needed). This is the
regression safety net for the EngineResponse contract change."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage
from app.models.customer import Customer
from app.schemas.auth import CurrentUser
from app.services.chat import ChatService


class TestSendMessageBaseline:
    def test_creates_conversation_and_persists_both_messages(self, test_db: Session, owner_user: CurrentUser):
        service = ChatService(test_db)
        resp = service.send_message("Hello there", owner_user.business_id, owner_user.user_id)

        assert resp.reply.startswith("[AI not configured")
        assert resp.actions == []
        assert resp.conversation_id is not None

        history = service.repo.get_recent_messages(resp.conversation_id, limit=10)
        # Two rapid-fire inserts can land on the same func.now() tick under
        # SQLite's coarser clock (a non-issue on Postgres' microsecond
        # precision in production) - don't depend on relative order here.
        assert {m.role for m in history} == {"user", "assistant"}
        user_msg = next(m for m in history if m.role == "user")
        assert user_msg.content == "Hello there"

    def test_reuses_conversation_when_id_provided(self, test_db: Session, owner_user: CurrentUser):
        service = ChatService(test_db)
        first = service.send_message("First message", owner_user.business_id, owner_user.user_id)
        second = service.send_message(
            "Second message", owner_user.business_id, owner_user.user_id, conversation_id=first.conversation_id
        )
        assert second.conversation_id == first.conversation_id
        history = service.repo.get_recent_messages(first.conversation_id, limit=10)
        assert len(history) == 4

    def test_conversation_owned_by_another_user_starts_a_new_one(
        self, test_db: Session, owner_user: CurrentUser, manager_user: CurrentUser
    ):
        service = ChatService(test_db)
        owner_conv = service.send_message("Owner's message", owner_user.business_id, owner_user.user_id)
        manager_resp = service.send_message(
            "Manager's message", manager_user.business_id, manager_user.user_id,
            conversation_id=owner_conv.conversation_id,
        )
        assert manager_resp.conversation_id != owner_conv.conversation_id

    def test_resolves_client_mention(self, test_db: Session, owner_user: CurrentUser, sample_customer: Customer):
        service = ChatService(test_db)
        resp = service.send_message(f"@client:{sample_customer.name} status?", owner_user.business_id, owner_user.user_id)
        assert len(resp.resolved_mentions) == 1
        assert resp.resolved_mentions[0]["found"] is True
        assert resp.resolved_mentions[0]["entity_id"] == str(sample_customer.id)

    def test_unresolvable_mention_reports_not_found(self, test_db: Session, owner_user: CurrentUser):
        service = ChatService(test_db)
        resp = service.send_message("@client:NoSuchCompany hi", owner_user.business_id, owner_user.user_id)
        assert resp.resolved_mentions[0]["found"] is False

    def test_history_limit_is_respected(self, test_db: Session, owner_user: CurrentUser, monkeypatch):
        monkeypatch.setattr("app.services.chat.settings.ai_conversation_history_limit", 2)
        service = ChatService(test_db)
        r1 = service.send_message("one", owner_user.business_id, owner_user.user_id)
        r2 = service.send_message("two", owner_user.business_id, owner_user.user_id, conversation_id=r1.conversation_id)
        r3 = service.send_message("three", owner_user.business_id, owner_user.user_id, conversation_id=r1.conversation_id)

        # func.now() ticks can tie under SQLite's clock when three sends
        # happen back-to-back in the same test (a non-issue on Postgres'
        # microsecond precision in production) - force strictly increasing
        # timestamps, in the known true send order, so the LIMIT/ORDER BY
        # mechanism itself is what's under test, not clock precision.
        ordered_ids = [
            r1.user_message_id, r1.assistant_message_id,
            r2.user_message_id, r2.assistant_message_id,
            r3.user_message_id, r3.assistant_message_id,
        ]
        base = datetime.now(timezone.utc)
        for i, msg_id in enumerate(ordered_ids):
            test_db.query(ChatMessage).filter(ChatMessage.id == msg_id).update(
                {"created_at": base + timedelta(seconds=i)}
            )
        test_db.commit()

        history = service.repo.get_recent_messages(r1.conversation_id, limit=2)
        assert len(history) == 2
        assert history[0].role == "user" and history[0].content == "three"
        assert history[1].role == "assistant" and "three" in history[1].content

    def test_engine_exception_becomes_error_reply_not_a_crash(self, test_db: Session, owner_user: CurrentUser, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError("engine exploded")

        monkeypatch.setattr("app.services.chat.get_engine", lambda: type("E", (), {"chat": staticmethod(_boom)})())
        service = ChatService(test_db)
        resp = service.send_message("hello", owner_user.business_id, owner_user.user_id)
        assert resp.reply == "[AI error: engine exploded]"
        assert resp.actions == []
