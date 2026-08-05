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
    NoArchiveFolderError,
    archive_message,
    delete_message,
    get_message,
    list_folders,
    list_messages,
    set_message_flags,
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
    list_responses: list[bytes] = []
    selected_mailboxes: list[str] = []
    store_calls: list[tuple] = []
    copy_calls: list[tuple] = []
    expunge_called = False

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
        _FakeImap4.selected_mailboxes.append(mailbox)
        if _FakeImap4.select_should_fail:
            return ("NO", [b"Could not open"])
        return ("OK", [b"1"])

    def list(self, directory='""', pattern="*"):
        return ("OK", list(_FakeImap4.list_responses))

    def uid(self, command, *args):
        if command == "search":
            return ("OK", [b" ".join(_FakeImap4.uids)])
        if command == "fetch":
            requested_uid = args[0]
            response = _FakeImap4.fetch_responses.get(requested_uid)
            if response is None:
                return ("OK", [None])
            return ("OK", [response])
        if command == "store":
            _FakeImap4.store_calls.append(args)
            return ("OK", [b"Store completed"])
        if command == "copy":
            _FakeImap4.copy_calls.append(args)
            return ("OK", [b"Copy completed"])
        raise ValueError(f"unexpected uid command {command!r}")

    def expunge(self):
        _FakeImap4.expunge_called = True
        return ("OK", [b"1"])

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
    _FakeImap4.list_responses = []
    _FakeImap4.selected_mailboxes = []
    _FakeImap4.store_calls = []
    _FakeImap4.copy_calls = []
    _FakeImap4.expunge_called = False
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


class TestListFolders:
    def test_special_use_attribute_resolves_role(self):
        _FakeImap4.list_responses = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Sent) "/" "Sent"',
            b'(\\HasNoChildren \\Trash) "/" "Trash"',
        ]
        folders = list_folders("imap.example.com", 993, "user", "pass")
        roles = {f.name: f.role for f in folders}
        assert roles == {"INBOX": "inbox", "Sent": "sent", "Trash": "trash"}

    def test_gmail_all_mail_maps_to_archive_role(self):
        _FakeImap4.list_responses = [
            b'(\\HasNoChildren \\All) "/" "[Gmail]/All Mail"',
        ]
        folders = list_folders("imap.example.com", 993, "user", "pass")
        assert folders[0].role == "archive"

    def test_name_fallback_when_no_special_use_attribute(self):
        _FakeImap4.list_responses = [
            b'(\\HasNoChildren) "/" "Sent Items"',
            b'(\\HasNoChildren) "/" "Deleted Items"',
            b'(\\HasNoChildren) "/" "Notes"',
        ]
        folders = list_folders("imap.example.com", 993, "user", "pass")
        roles = {f.name: f.role for f in folders}
        assert roles["Sent Items"] == "sent"
        assert roles["Deleted Items"] == "trash"
        assert roles["Notes"] is None

    def test_list_folders_does_not_select_a_mailbox(self):
        _FakeImap4.list_responses = [b'(\\HasNoChildren) "/" "INBOX"']
        list_folders("imap.example.com", 993, "user", "pass")
        assert _FakeImap4.selected_mailboxes == []


class TestListMessagesFolderAndStarred:
    def test_folder_param_selects_that_mailbox(self):
        _FakeImap4.fetch_responses = {}
        _FakeImap4.uids = []
        list_messages("imap.example.com", 993, "user", "pass", folder="Sent")
        assert _FakeImap4.selected_mailboxes == ["Sent"]

    def test_only_flagged_uses_flagged_search(self):
        _FakeImap4.fetch_responses = {
            b"1": (b"1 (UID 1 FLAGS (\\Flagged))", b"From: a@example.com\r\nSubject: One\r\nDate: \r\n\r\n"),
        }
        _FakeImap4.uids = [b"1"]
        results = list_messages("imap.example.com", 993, "user", "pass", only_flagged=True)
        assert len(results) == 1
        assert results[0].is_starred is True

    def test_default_search_is_not_flagged_only(self):
        _FakeImap4.fetch_responses = {
            b"1": (b"1 (UID 1 FLAGS ())", b"From: a@example.com\r\nSubject: One\r\nDate: \r\n\r\n"),
        }
        _FakeImap4.uids = [b"1"]
        results = list_messages("imap.example.com", 993, "user", "pass")
        assert results[0].is_starred is False


class TestSetMessageFlags:
    def test_star_on_sends_plus_flags(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5", is_starred=True)
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Flagged)")]

    def test_star_off_sends_minus_flags(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5", is_starred=False)
        assert _FakeImap4.store_calls == [("5", "-FLAGS", "(\\Flagged)")]

    def test_mark_read_sends_seen_flag(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5", is_read=True)
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Seen)")]

    def test_mark_unread_sends_minus_seen_flag(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5", is_read=False)
        assert _FakeImap4.store_calls == [("5", "-FLAGS", "(\\Seen)")]

    def test_both_flags_sends_two_store_calls(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5", is_starred=True, is_read=True)
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Flagged)"), ("5", "+FLAGS", "(\\Seen)")]

    def test_neither_flag_sends_zero_store_calls(self):
        set_message_flags("imap.example.com", 993, "user", "pass", "5")
        assert _FakeImap4.store_calls == []


class TestArchiveMessage:
    def test_moves_to_resolved_archive_folder(self):
        _FakeImap4.list_responses = [b'(\\HasNoChildren \\Archive) "/" "Archive"']
        resolved = archive_message("imap.example.com", 993, "user", "pass", "5")
        assert resolved == "Archive"
        assert _FakeImap4.copy_calls == [("5", "Archive")]
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Deleted)")]
        assert _FakeImap4.expunge_called is True

    def test_no_archive_folder_raises(self):
        _FakeImap4.list_responses = [b'(\\HasNoChildren) "/" "INBOX"']
        with pytest.raises(NoArchiveFolderError):
            archive_message("imap.example.com", 993, "user", "pass", "5")
        assert _FakeImap4.copy_calls == []


class TestDeleteMessage:
    def test_moves_to_trash_when_not_already_in_trash(self):
        _FakeImap4.list_responses = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Trash) "/" "Trash"',
        ]
        delete_message("imap.example.com", 993, "user", "pass", "5", source_folder="INBOX")
        assert _FakeImap4.copy_calls == [("5", "Trash")]
        assert _FakeImap4.expunge_called is True

    def test_permanently_deletes_when_already_in_trash(self):
        _FakeImap4.list_responses = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Trash) "/" "Trash"',
        ]
        delete_message("imap.example.com", 993, "user", "pass", "5", source_folder="Trash")
        assert _FakeImap4.copy_calls == []
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Deleted)")]
        assert _FakeImap4.expunge_called is True

    def test_permanently_deletes_when_no_trash_folder_exists(self):
        _FakeImap4.list_responses = [b'(\\HasNoChildren) "/" "INBOX"']
        delete_message("imap.example.com", 993, "user", "pass", "5", source_folder="INBOX")
        assert _FakeImap4.copy_calls == []
        assert _FakeImap4.store_calls == [("5", "+FLAGS", "(\\Deleted)")]
        assert _FakeImap4.expunge_called is True


class TestAttachments:
    def test_message_with_attachment_populates_attachments_list(self):
        _FakeImap4.fetch_responses = {
            "7": (
                b"1 (UID 7 RFC822 {1})",
                b'Content-Type: multipart/mixed; boundary="B"\r\n'
                b"From: a@example.com\r\nTo: me@example.com\r\nSubject: Report\r\nDate: \r\n\r\n"
                b"--B\r\n"
                b"Content-Type: text/plain\r\n\r\n"
                b"Body text.\r\n"
                b"--B\r\n"
                b'Content-Type: application/pdf\r\nContent-Disposition: attachment; filename="report.pdf"\r\n\r\n'
                b"PDFDATA"
                b"\r\n--B--\r\n",
            )
        }
        detail = get_message("imap.example.com", 993, "user", "pass", "7")
        assert detail.attachment_count == 1
        assert detail.attachments[0].filename == "report.pdf"
        assert detail.attachments[0].content_type == "application/pdf"

    def test_message_without_attachment_has_empty_list(self):
        _FakeImap4.fetch_responses = {
            "8": (
                b"1 (UID 8 RFC822 {1})",
                b"From: a@example.com\r\nTo: me@example.com\r\nSubject: Hi\r\nDate: \r\n\r\nJust text.",
            )
        }
        detail = get_message("imap.example.com", 993, "user", "pass", "8")
        assert detail.attachment_count == 0
        assert detail.attachments == []
