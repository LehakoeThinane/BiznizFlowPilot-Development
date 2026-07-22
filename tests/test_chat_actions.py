"""API/service tests for the pending-action confirm/cancel wiring in
app/api/chat.py + app/services/chat.py. ACTION_EXECUTORS is monkeypatched to
stubs so no real TaskService/LeadService/CustomerService call is needed to
test the wiring itself (that's covered separately in
tests/test_chat_tools_executors.py)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.repositories.chat import ChatRepository
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


def _make_pending_message(test_db: Session, owner_user: CurrentUser, action_id: str | None = None):
    repo = ChatRepository(test_db)
    conv = repo.create_conversation(owner_user.business_id, owner_user.user_id, title="Test")
    action = {
        "id": action_id or str(uuid4()),
        "action_type": "create_task",
        "arguments": {"title": "Follow up"},
        "description": "Create a follow-up task",
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "resolved_at": None,
    }
    msg = repo.add_message(conv.id, role="assistant", content="I'd like to do this", actions_data=[action])
    test_db.commit()
    return msg.id, action["id"]


class TestConfirmAction:
    def test_confirm_executes_and_returns_result(self, client, test_db: Session, owner_user: CurrentUser, monkeypatch):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        calls = []

        def _stub_executor(db, business_id, current_user, args):
            calls.append((business_id, current_user.user_id, args))
            return {"task_id": "abc123"}

        monkeypatch.setattr("app.services.chat.ACTION_EXECUTORS", {"create_task": _stub_executor})

        r = client.post(
            f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm", headers=_auth_headers(owner_user)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["action"]["status"] == "executed"
        assert body["action"]["result"] == {"task_id": "abc123"}
        assert len(calls) == 1
        assert calls[0][0] == owner_user.business_id
        assert calls[0][2] == {"title": "Follow up"}

    def test_confirm_when_executor_raises_marks_failed_not_500(self, client, test_db: Session, owner_user: CurrentUser, monkeypatch):
        msg_id, action_id = _make_pending_message(test_db, owner_user)

        def _stub_executor(db, business_id, current_user, args):
            raise ValueError("Invalid state transition: new -> won")

        monkeypatch.setattr("app.services.chat.ACTION_EXECUTORS", {"create_task": _stub_executor})

        r = client.post(
            f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm", headers=_auth_headers(owner_user)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["action"]["status"] == "failed"
        assert "Invalid state transition" in body["action"]["error"]

    def test_confirm_already_executed_action_returns_409(self, client, test_db: Session, owner_user: CurrentUser, monkeypatch):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        calls = []
        monkeypatch.setattr(
            "app.services.chat.ACTION_EXECUTORS",
            {"create_task": lambda db, business_id, current_user, args: (calls.append(1), {"ok": True})[1]},
        )

        r1 = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm", headers=_auth_headers(owner_user))
        assert r1.status_code == 200
        r2 = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm", headers=_auth_headers(owner_user))
        assert r2.status_code == 409
        assert len(calls) == 1  # executor not called a second time

    def test_confirm_unknown_action_id_returns_404(self, client, test_db: Session, owner_user: CurrentUser):
        msg_id, _ = _make_pending_message(test_db, owner_user)
        r = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{uuid4()}/confirm", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_confirm_unknown_message_id_returns_404(self, client, owner_user: CurrentUser):
        r = client.post(f"/api/v1/chat/messages/{uuid4()}/actions/{uuid4()}/confirm", headers=_auth_headers(owner_user))
        assert r.status_code == 404

    def test_cross_user_access_returns_404(self, client, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        r = client.post(
            f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm", headers=_auth_headers(other_user)
        )
        assert r.status_code == 404

    def test_requires_auth(self, client, test_db: Session, owner_user: CurrentUser):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        r = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/confirm")
        assert r.status_code == 401


class TestCancelAction:
    def test_cancel_pending_action(self, client, test_db: Session, owner_user: CurrentUser):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        r = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/cancel", headers=_auth_headers(owner_user))
        assert r.status_code == 200
        assert r.json()["action"]["status"] == "cancelled"

    def test_cancel_already_cancelled_returns_409(self, client, test_db: Session, owner_user: CurrentUser):
        msg_id, action_id = _make_pending_message(test_db, owner_user)
        client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/cancel", headers=_auth_headers(owner_user))
        r2 = client.post(f"/api/v1/chat/messages/{msg_id}/actions/{action_id}/cancel", headers=_auth_headers(owner_user))
        assert r2.status_code == 409
