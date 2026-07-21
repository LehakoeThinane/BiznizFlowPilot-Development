"""Orchestration tests for app/integrations/imap_client.py - mocks imaplib
itself (list_messages/get_message/imap_connection), following the same
fake-class-monkeypatch shape as test_email_provider_idempotency.py's _FakeSMTP."""

from __future__ import annotations

import imaplib

import pytest

from app.integrations.imap_client import (
    ImapAuthenticationError,
    ImapConnectionError,
    ImapError,
    get_message,
    list_messages,
)


class _FakeImap4:
    """Fake imaplib.IMAP4/IMAP4_SSL. login_should_fail / select_should_fail
    let individual tests trigger the failure branches.

    Since tests monkeypatch imaplib.IMAP4 itself to this class, production
    code's `imaplib.IMAP4.error` references resolve to `_FakeImap4.error` -
    so the real exception class must be captured here before patching.
    """

    error = imaplib.IMAP4.error
    login_should_fail = False
    select_should_fail = False
    uids: list[bytes] = [b"1", b"2", b"3"]
    fetch_responses: dict[bytes, tuple] = {}

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def starttls(self):
        pass

    def login(self, username, password):
        if _FakeImap4.login_should_fail:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")
        return ("OK", [b"Logged in"])

    def select(self, mailbox):
        if _FakeImap4.select_should_fail:
            return ("NO", [b"Could not open"])
        return ("OK", [b"1"])

    def uid(self, command, *args):
        if command == "search":
            return ("OK", [b" ".join(_FakeImap4.uids)])
        if command == "fetch":
            requested_uid = args[0]
            response = _FakeImap4.fetch_responses.get(requested_uid)
            if response is None:
                return ("OK", [None])
            return ("OK", [response])
        raise ValueError(f"unexpected uid command {command!r}")

    def close(self):
        pass

    def logout(self):
        pass


@pytest.fixture(autouse=True)
def _reset_fake_state():
    _FakeImap4.login_should_fail = False
    _FakeImap4.select_should_fail = False
    _FakeImap4.uids = [b"1", b"2", b"3"]
    _FakeImap4.fetch_responses = {}
    yield


@pytest.fixture(autouse=True)
def _patch_imaplib(monkeypatch):
    monkeypatch.setattr(imaplib, "IMAP4_SSL", _FakeImap4)
    monkeypatch.setattr(imaplib, "IMAP4", _FakeImap4)


class TestListMessages:
    def test_returns_summaries_newest_first(self):
        _FakeImap4.fetch_responses = {
            b"1": (b"1 (UID 1 FLAGS (\\Seen))", b"From: a@example.com\r\nSubject: One\r\nDate: Mon, 1 Jan 2026 10:00:00\r\n\r\n"),
            b"2": (b"2 (UID 2 FLAGS ())", b"From: b@example.com\r\nSubject: Two\r\nDate: Tue, 2 Jan 2026 10:00:00\r\n\r\n"),
            b"3": (b"3 (UID 3 FLAGS (\\Seen \\Answered))", b"From: c@example.com\r\nSubject: Three\r\nDate: Wed, 3 Jan 2026 10:00:00\r\n\r\n"),
        }
        results = list_messages("imap.example.com", 993, "user", "pass")
        assert [m.uid for m in results] == ["3", "2", "1"]
        assert results[0].is_read is True
        assert results[1].is_read is False
        assert results[2].subject == "One"

    def test_respects_limit_and_offset(self):
        _FakeImap4.fetch_responses = {
            uid: (f"{i} (UID {i} FLAGS ())".encode(), b"From: x@example.com\r\nSubject: X\r\nDate: \r\n\r\n")
            for i, uid in enumerate([b"1", b"2", b"3"], start=1)
        }
        results = list_messages("imap.example.com", 993, "user", "pass", limit=1, offset=1)
        assert len(results) == 1
        assert results[0].uid == "2"

    def test_login_failure_raises_authentication_error(self):
        _FakeImap4.login_should_fail = True
        with pytest.raises(ImapAuthenticationError):
            list_messages("imap.example.com", 993, "user", "wrong-pass")

    def test_select_failure_raises_connection_error(self):
        _FakeImap4.select_should_fail = True
        with pytest.raises(ImapConnectionError):
            list_messages("imap.example.com", 993, "user", "pass")

    def test_port_143_uses_starttls_variant(self):
        _FakeImap4.fetch_responses = {}
        _FakeImap4.uids = []
        results = list_messages("imap.example.com", 143, "user", "pass")
        assert results == []


class TestGetMessage:
    def test_happy_path(self):
        _FakeImap4.fetch_responses = {
            "5": (
                b"1 (UID 5 RFC822 {123})",
                b"From: a@example.com\r\nTo: me@example.com\r\nSubject: Hi\r\nDate: Mon, 1 Jan 2026 10:00:00\r\n\r\nBody.",
            )
        }
        detail = get_message("imap.example.com", 993, "user", "pass", "5")
        assert detail.uid == "5"
        assert detail.from_address == "a@example.com"
        assert detail.body_text == "Body."

    def test_missing_message_raises_imap_error(self):
        _FakeImap4.fetch_responses = {}
        with pytest.raises(ImapError):
            get_message("imap.example.com", 993, "user", "pass", "999")
