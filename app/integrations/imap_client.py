"""Generic IMAP client for the per-user email inbox feature.

No existing pattern in this codebase to mirror - reading mail via IMAP is
genuinely new. Uses only the Python standard library (imaplib + email),
no new pip dependency. Deliberately simple for v1: one connection per
request (open -> use -> logout), no persistent connection pooling, no
local message cache - "prove the pipe first."

Everything that can be unit-tested without a real/mocked IMAP server
(MIME parsing, header decoding) is a pure function taking already-fetched
bytes. Only the connection/search/fetch orchestration needs imaplib itself
mocked in tests.
"""

from __future__ import annotations

import imaplib
import re
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from typing import Iterator

_UID_RE = re.compile(rb"UID (\d+)")
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)")


class ImapError(Exception):
    """Base exception for IMAP failures."""


class ImapConnectionError(ImapError):
    """Host/port unreachable, TLS handshake failure, timeout, or INBOX couldn't be opened."""


class ImapAuthenticationError(ImapError):
    """The server rejected the username/password."""


@dataclass(slots=True)
class MessageSummary:
    uid: str
    from_address: str
    subject: str
    date: str | None
    is_read: bool
    has_attachments: bool = False


@dataclass(slots=True)
class MessageDetail:
    uid: str
    from_address: str
    to_address: str
    subject: str
    date: str | None
    body_html: str | None
    body_text: str | None
    attachment_count: int = 0


def decode_mime_header(raw: str | None) -> str:
    """Decode an RFC 2047 encoded-word header (e.g. '=?UTF-8?B?...?=') into
    plain text. Falls back to the raw string unchanged if decoding fails."""
    if not raw:
        return ""
    try:
        parts = decode_header(raw)
        decoded = []
        for text, charset in parts:
            if isinstance(text, bytes):
                decoded.append(text.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(text)
        return "".join(decoded)
    except Exception:
        return raw


def _extract_body(msg: Message) -> tuple[str | None, str | None, int]:
    """Walk MIME parts, returning (body_html, body_text, attachment_count).
    Prefers html but also populates text if a plain part exists - some
    senders only include one or the other."""
    body_html: str | None = None
    body_text: str | None = None
    attachment_count = 0

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition") or "")

        if "attachment" in disposition or part.get_filename():
            attachment_count += 1
            continue

        if part.is_multipart():
            continue

        if content_type == "text/html" and body_html is None:
            payload = part.get_payload(decode=True)
            if payload is not None:
                charset = part.get_content_charset() or "utf-8"
                body_html = payload.decode(charset, errors="replace")
        elif content_type == "text/plain" and body_text is None:
            payload = part.get_payload(decode=True)
            if payload is not None:
                charset = part.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")

    return body_html, body_text, attachment_count


def parse_envelope_row(uid: str, header_bytes: bytes, is_seen: bool) -> MessageSummary:
    """Parse a header-only FETCH response (From/Subject/Date) into a summary row."""
    msg = message_from_bytes(header_bytes)
    return MessageSummary(
        uid=uid,
        from_address=decode_mime_header(msg.get("From")),
        subject=decode_mime_header(msg.get("Subject")),
        date=msg.get("Date"),
        is_read=is_seen,
    )


def parse_full_message(uid: str, raw_bytes: bytes) -> MessageDetail:
    """Parse a full RFC822 message into a detail view."""
    msg = message_from_bytes(raw_bytes)
    body_html, body_text, attachment_count = _extract_body(msg)
    return MessageDetail(
        uid=uid,
        from_address=decode_mime_header(msg.get("From")),
        to_address=decode_mime_header(msg.get("To")),
        subject=decode_mime_header(msg.get("Subject")),
        date=msg.get("Date"),
        body_html=body_html,
        body_text=body_text,
        attachment_count=attachment_count,
    )


@contextmanager
def imap_connection(host: str, port: int, username: str, password: str, timeout: int = 10) -> Iterator[imaplib.IMAP4]:
    """Open, login, SELECT INBOX, yield the connection, always logout.

    Port 993 is IMAP's conventional implicit-SSL port (note this differs
    from SMTP's 465 - the two protocols use different implicit-SSL ports
    by convention, this is not a copy-paste inconsistency). Any other port
    uses plaintext IMAP4 + STARTTLS.

    Connection/TLS failures and login failures are mapped to different
    exception types - imaplib raises the same imaplib.IMAP4.error class for
    both, so they must be caught in separate try blocks to tell them apart.
    """
    try:
        if port == 993:
            conn = imaplib.IMAP4_SSL(host, port, timeout=timeout)
        else:
            conn = imaplib.IMAP4(host, port, timeout=timeout)
            conn.starttls()
    except (imaplib.IMAP4.error, socket.timeout, OSError) as e:
        raise ImapConnectionError(f"Could not connect to {host}:{port} - {e}") from e

    try:
        typ, _ = conn.login(username, password)
        if typ != "OK":
            raise ImapAuthenticationError("Login failed - check your IMAP username/password.")
    except imaplib.IMAP4.error as e:
        raise ImapAuthenticationError(f"Login failed - check your IMAP username/password. ({e})") from e

    try:
        typ, _ = conn.select("INBOX")
        if typ != "OK":
            raise ImapConnectionError("Could not open INBOX.")
    except imaplib.IMAP4.error as e:
        raise ImapConnectionError(f"Could not open INBOX - {e}") from e

    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass


def list_messages(host: str, port: int, username: str, password: str, limit: int = 50, offset: int = 0) -> list[MessageSummary]:
    """List the most recent messages in INBOX, newest first.

    Uses BODY.PEEK (not BODY) so listing never marks messages as read -
    that's a side effect only get_message() should cause.
    """
    with imap_connection(host, port, username, password) as conn:
        try:
            typ, data = conn.uid("search", None, "ALL")
            if typ != "OK":
                raise ImapConnectionError("Could not search INBOX.")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not search INBOX - {e}") from e

        all_uids = data[0].split() if data and data[0] else []
        all_uids = list(reversed(all_uids))  # newest first
        page_uids = all_uids[offset:offset + limit]

        summaries: list[MessageSummary] = []
        for raw_uid in page_uids:
            try:
                typ, fetch_data = conn.uid(
                    "fetch", raw_uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
                )
                if typ != "OK" or not fetch_data or fetch_data[0] is None:
                    continue
            except imaplib.IMAP4.error as e:
                raise ImapConnectionError(f"Could not fetch message {raw_uid!r} - {e}") from e

            meta, header_bytes = fetch_data[0]
            flags_match = _FLAGS_RE.search(meta)
            is_seen = bool(flags_match and b"\\Seen" in flags_match.group(1))
            summaries.append(parse_envelope_row(raw_uid.decode(), header_bytes, is_seen))

        return summaries


def get_message(host: str, port: int, username: str, password: str, uid: str) -> MessageDetail:
    """Fetch and parse one full message by UID. This is a real (non-PEEK)
    fetch - opening a message correctly marks it \\Seen, unlike listing."""
    with imap_connection(host, port, username, password) as conn:
        try:
            typ, fetch_data = conn.uid("fetch", uid, "(RFC822)")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not fetch message {uid!r} - {e}") from e

        if typ != "OK" or not fetch_data or fetch_data[0] is None:
            raise ImapError(f"Message {uid!r} not found.")

        _, raw_bytes = fetch_data[0]
        return parse_full_message(uid, raw_bytes)
