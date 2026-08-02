"""SMTPEmailProvider attachment support - emailing a document from the
in-app editor needs the outgoing message to actually carry the file, not
just the body text."""

from __future__ import annotations

from app.workflow_engine.email_provider import EmailAttachment, SMTPEmailProvider


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
    return SMTPEmailProvider(host="localhost", port=1025, default_from_email="ops@biznizflowpilot.local")


def test_send_without_attachments_is_unaffected(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()

    provider.send(recipient="a@example.com", subject="Hi", body="Body")

    sent = _FakeSMTP.sent_messages[0]
    assert not sent.is_multipart() or sum(1 for _ in sent.iter_attachments()) == 0


def test_attachment_is_included_with_filename_and_content(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()
    attachment = EmailAttachment(filename="report.pdf", content=b"%PDF-fake-bytes", mime_type="application/pdf")

    provider.send(recipient="a@example.com", subject="Report", body="See attached", attachments=[attachment])

    sent = _FakeSMTP.sent_messages[0]
    parts = list(sent.iter_attachments())
    assert len(parts) == 1
    assert parts[0].get_filename() == "report.pdf"
    assert parts[0].get_content_type() == "application/pdf"
    assert parts[0].get_payload(decode=True) == b"%PDF-fake-bytes"


def test_multiple_attachments_are_all_included(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()
    attachments = [
        EmailAttachment(filename="doc.html", content=b"<p>hi</p>", mime_type="text/html"),
        EmailAttachment(filename="notes.txt", content=b"plain text", mime_type="text/plain"),
    ]

    provider.send(recipient="a@example.com", subject="Docs", body="Body", attachments=attachments)

    sent = _FakeSMTP.sent_messages[0]
    filenames = {p.get_filename() for p in sent.iter_attachments()}
    assert filenames == {"doc.html", "notes.txt"}


def test_attachment_without_slash_mime_type_falls_back_to_octet_stream(monkeypatch):
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    _FakeSMTP.sent_messages = []
    provider = _provider()
    attachment = EmailAttachment(filename="mystery.bin", content=b"bytes", mime_type="")

    provider.send(recipient="a@example.com", subject="Hi", body="Body", attachments=[attachment])

    sent = _FakeSMTP.sent_messages[0]
    parts = list(sent.iter_attachments())
    assert parts[0].get_content_type() == "application/octet-stream"
