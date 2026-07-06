"""SMTPEmailProvider Message-ID idempotency behavior.

make_msgid() mixes in a timestamp/pid/random component on every call, so it
can't be used for retry dedup even with the same idstring twice - the fix is
building the Message-ID directly from the caller-supplied idempotency_key.
"""

from __future__ import annotations

from app.workflow_engine.email_provider import SMTPEmailProvider


class _FakeSMTP:
    sent_messages: list = []

    def __init__(self, host, port, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def ehlo(self):
        pass

    def send_message(self, message):
        _FakeSMTP.sent_messages.append(message)
        return {}


def _provider() -> SMTPEmailProvider:
    return SMTPEmailProvider(
        host="localhost", port=1025, default_from_email="ops@biznizflowpilot.local",
    )


def test_same_idempotency_key_produces_same_message_id(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()

    provider.send(recipient="a@example.com", subject="Hi", body="Body", idempotency_key="action-123")
    provider.send(recipient="a@example.com", subject="Hi", body="Body", idempotency_key="action-123")

    first_id = _FakeSMTP.sent_messages[0]["Message-ID"]
    second_id = _FakeSMTP.sent_messages[1]["Message-ID"]
    assert first_id == second_id
    assert "action-123" in first_id


def test_different_idempotency_keys_produce_different_message_ids(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()

    provider.send(recipient="a@example.com", subject="Hi", body="Body", idempotency_key="action-1")
    provider.send(recipient="a@example.com", subject="Hi", body="Body", idempotency_key="action-2")

    first_id = _FakeSMTP.sent_messages[0]["Message-ID"]
    second_id = _FakeSMTP.sent_messages[1]["Message-ID"]
    assert first_id != second_id


def test_no_idempotency_key_falls_back_to_random_message_id(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()

    provider.send(recipient="a@example.com", subject="Hi", body="Body")
    provider.send(recipient="a@example.com", subject="Hi", body="Body")

    first_id = _FakeSMTP.sent_messages[0]["Message-ID"]
    second_id = _FakeSMTP.sent_messages[1]["Message-ID"]
    assert first_id != second_id
