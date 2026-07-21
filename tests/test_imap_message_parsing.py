"""Pure MIME-parsing/header-decoding tests for app/integrations/imap_client.py.
No IMAP server or mocking needed - these operate on hand-built raw bytes."""

from __future__ import annotations

from app.integrations.imap_client import decode_mime_header, parse_envelope_row, parse_full_message


class TestDecodeMimeHeader:
    def test_plain_header_passthrough(self):
        assert decode_mime_header("Hello there") == "Hello there"

    def test_none_returns_empty_string(self):
        assert decode_mime_header(None) == ""

    def test_rfc2047_encoded_word_is_decoded(self):
        assert decode_mime_header("=?UTF-8?B?SGVsbG8gV29ybGQ=?=") == "Hello World"


class TestParseEnvelopeRow:
    def test_plain_header_seen(self):
        header = b"From: Alice <alice@example.com>\r\nSubject: Hello there\r\nDate: Mon, 1 Jan 2026 10:00:00 +0000\r\n\r\n"
        summary = parse_envelope_row("123", header, True)
        assert summary.uid == "123"
        assert summary.from_address == "Alice <alice@example.com>"
        assert summary.subject == "Hello there"
        assert summary.date == "Mon, 1 Jan 2026 10:00:00 +0000"
        assert summary.is_read is True

    def test_encoded_subject_unseen(self):
        header = (
            b"From: Bob <bob@example.com>\r\n"
            b"Subject: =?UTF-8?B?SGVsbG8gV29ybGQ=?=\r\n"
            b"Date: Tue, 2 Jan 2026 10:00:00 +0000\r\n\r\n"
        )
        summary = parse_envelope_row("124", header, False)
        assert summary.subject == "Hello World"
        assert summary.is_read is False


class TestParseFullMessage:
    def test_plain_text_only_message(self):
        raw = (
            b"From: Carol <carol@example.com>\r\n"
            b"To: me@example.com\r\n"
            b"Subject: Plain text\r\n"
            b"Date: Wed, 3 Jan 2026 10:00:00 +0000\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Just a plain body."
        )
        detail = parse_full_message("125", raw)
        assert detail.from_address == "Carol <carol@example.com>"
        assert detail.to_address == "me@example.com"
        assert detail.body_text == "Just a plain body."
        assert detail.body_html is None
        assert detail.attachment_count == 0

    def test_multipart_alternative_prefers_html(self):
        raw = (
            b"From: Carol <carol@example.com>\r\n"
            b"To: me@example.com\r\n"
            b"Subject: Multipart test\r\n"
            b"Date: Wed, 3 Jan 2026 10:00:00 +0000\r\n"
            b"MIME-Version: 1.0\r\n"
            b'Content-Type: multipart/alternative; boundary="BOUND"\r\n\r\n'
            b"--BOUND\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Plain body here.\r\n"
            b"--BOUND\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n\r\n"
            b"<p>HTML body here.</p>\r\n"
            b"--BOUND--\r\n"
        )
        detail = parse_full_message("126", raw)
        assert detail.body_html == "<p>HTML body here.</p>"
        assert detail.body_text == "Plain body here."
        assert detail.attachment_count == 0

    def test_multipart_mixed_with_attachment_is_counted_not_included(self):
        raw = (
            b"From: Dan <dan@example.com>\r\n"
            b"To: me@example.com\r\n"
            b"Subject: With attachment\r\n"
            b"Date: Thu, 4 Jan 2026 10:00:00 +0000\r\n"
            b"MIME-Version: 1.0\r\n"
            b'Content-Type: multipart/mixed; boundary="BOUND"\r\n\r\n'
            b"--BOUND\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Body text.\r\n"
            b"--BOUND\r\n"
            b'Content-Type: application/pdf; name="doc.pdf"\r\n'
            b'Content-Disposition: attachment; filename="doc.pdf"\r\n'
            b"Content-Transfer-Encoding: base64\r\n\r\n"
            b"JVBERi0xLjQK\r\n"
            b"--BOUND--\r\n"
        )
        detail = parse_full_message("127", raw)
        assert detail.body_text == "Body text."
        assert detail.attachment_count == 1
        assert "JVBERi" not in (detail.body_text or "")
        assert detail.body_html is None
