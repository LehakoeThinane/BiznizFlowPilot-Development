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
from dataclasses import dataclass, field
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from typing import Iterator

_UID_RE = re.compile(rb"UID (\d+)")
_FLAGS_RE = re.compile(rb"FLAGS \(([^)]*)\)")
_LIST_RE = re.compile(rb'^\((?P<attrs>[^)]*)\)\s+"(?P<delim>[^"]*)"\s+(?P<name>.+)$')
_SIMPLE_MAILBOX_RE = re.compile(r"^[A-Za-z0-9_.\-\[\]/]+$")

_SPECIAL_USE_ROLES = {
    b"\\Sent": "sent",
    b"\\Drafts": "drafts",
    b"\\Trash": "trash",
    b"\\Archive": "archive",
    b"\\All": "archive",  # Gmail's "All Mail" - closest generic-IMAP equivalent of an archive
    b"\\Junk": "junk",
}
_NAME_FALLBACK_ROLES = [
    ("sent", "sent"),
    ("draft", "drafts"),
    ("trash", "trash"),
    ("deleted", "trash"),
    ("archive", "archive"),
    ("all mail", "archive"),
    ("junk", "junk"),
    ("spam", "junk"),
]


class ImapError(Exception):
    """Base exception for IMAP failures."""


class ImapConnectionError(ImapError):
    """Host/port unreachable, TLS handshake failure, timeout, or the requested folder couldn't be opened."""


class ImapAuthenticationError(ImapError):
    """The server rejected the username/password."""


class NoArchiveFolderError(ImapError):
    """No folder with an archive-like role (\\Archive, \\All, or name fallback) was found."""


@dataclass(slots=True)
class MessageSummary:
    uid: str
    from_address: str
    subject: str
    date: str | None
    is_read: bool
    is_starred: bool = False
    has_attachments: bool = False


@dataclass(slots=True)
class AttachmentInfo:
    filename: str
    size: int
    content_type: str


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
    attachments: list[AttachmentInfo] = field(default_factory=list)


@dataclass(slots=True)
class FolderInfo:
    name: str
    delimiter: str
    attributes: list[str]
    role: str | None


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


def _extract_body(msg: Message) -> tuple[str | None, str | None, list[AttachmentInfo]]:
    """Walk MIME parts, returning (body_html, body_text, attachments).
    Prefers html but also populates text if a plain part exists - some
    senders only include one or the other."""
    body_html: str | None = None
    body_text: str | None = None
    attachments: list[AttachmentInfo] = []

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition") or "")

        if "attachment" in disposition or part.get_filename():
            payload = part.get_payload(decode=True)
            attachments.append(AttachmentInfo(
                filename=decode_mime_header(part.get_filename()) or "attachment",
                size=len(payload) if payload else 0,
                content_type=content_type,
            ))
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

    return body_html, body_text, attachments


def parse_envelope_row(uid: str, header_bytes: bytes, is_seen: bool, is_flagged: bool = False) -> MessageSummary:
    """Parse a header-only FETCH response (From/Subject/Date) into a summary row."""
    msg = message_from_bytes(header_bytes)
    return MessageSummary(
        uid=uid,
        from_address=decode_mime_header(msg.get("From")),
        subject=decode_mime_header(msg.get("Subject")),
        date=msg.get("Date"),
        is_read=is_seen,
        is_starred=is_flagged,
    )


def parse_full_message(uid: str, raw_bytes: bytes) -> MessageDetail:
    """Parse a full RFC822 message into a detail view."""
    msg = message_from_bytes(raw_bytes)
    body_html, body_text, attachments = _extract_body(msg)
    return MessageDetail(
        uid=uid,
        from_address=decode_mime_header(msg.get("From")),
        to_address=decode_mime_header(msg.get("To")),
        subject=decode_mime_header(msg.get("Subject")),
        date=msg.get("Date"),
        body_html=body_html,
        body_text=body_text,
        attachment_count=len(attachments),
        attachments=attachments,
    )


def _quote_mailbox(name: str) -> str:
    """Quote an IMAP mailbox name per the quoted-string grammar, unless it's
    already a simple atom (no spaces/special chars) that doesn't need it."""
    if _SIMPLE_MAILBOX_RE.match(name):
        return name
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _resolve_role(name: str, attributes: list[bytes]) -> str | None:
    if name.upper() == "INBOX":
        return "inbox"
    for attr in attributes:
        role = _SPECIAL_USE_ROLES.get(attr)
        if role:
            return role
    lowered = name.lower()
    for needle, role in _NAME_FALLBACK_ROLES:
        if needle in lowered:
            return role
    return None


@contextmanager
def imap_connection(
    host: str, port: int, username: str, password: str, timeout: int = 10, folder: str | None = "INBOX"
) -> Iterator[imaplib.IMAP4]:
    """Open, login, optionally SELECT a folder, yield the connection, always logout.

    Port 993 is IMAP's conventional implicit-SSL port (note this differs
    from SMTP's 465 - the two protocols use different implicit-SSL ports
    by convention, this is not a copy-paste inconsistency). Any other port
    uses plaintext IMAP4 + STARTTLS.

    Connection/TLS failures and login failures are mapped to different
    exception types - imaplib raises the same imaplib.IMAP4.error class for
    both, so they must be caught in separate try blocks to tell them apart.

    folder=None skips SELECT entirely - used by folder listing, which
    doesn't need (and shouldn't require) a mailbox to be open.
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

    if folder is not None:
        try:
            typ, _ = conn.select(_quote_mailbox(folder))
            if typ != "OK":
                raise ImapConnectionError(f"Could not open folder {folder!r}.")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not open folder {folder!r} - {e}") from e

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


def _list_folders_on_connection(conn: imaplib.IMAP4) -> list[FolderInfo]:
    try:
        typ, data = conn.list()
        if typ != "OK":
            raise ImapConnectionError("Could not list folders.")
    except imaplib.IMAP4.error as e:
        raise ImapConnectionError(f"Could not list folders - {e}") from e

    folders: list[FolderInfo] = []
    for line in data or []:
        if not line:
            continue
        match = _LIST_RE.match(line)
        if not match:
            continue  # unhandled edge case: literal-continuation ({n}) mailbox names
        attrs = match.group("attrs").split()
        delim = match.group("delim").decode()
        name = match.group("name").decode().strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        folders.append(FolderInfo(
            name=name,
            delimiter=delim,
            attributes=[a.decode() for a in attrs],
            role=_resolve_role(name, attrs),
        ))
    return folders


def list_folders(host: str, port: int, username: str, password: str) -> list[FolderInfo]:
    """List every folder on the mailbox, with a best-effort role resolved
    per folder (see _resolve_role) - the caller maps a fixed role vocabulary
    (inbox/sent/drafts/trash/archive/junk) to whatever a given provider
    actually calls its folders."""
    with imap_connection(host, port, username, password, folder=None) as conn:
        return _list_folders_on_connection(conn)


def list_messages(
    host: str, port: int, username: str, password: str,
    limit: int = 50, offset: int = 0, folder: str = "INBOX", only_flagged: bool = False,
) -> list[MessageSummary]:
    """List the most recent messages in a folder, newest first.

    Uses BODY.PEEK (not BODY) so listing never marks messages as read -
    that's a side effect only get_message() should cause.
    """
    with imap_connection(host, port, username, password, folder=folder) as conn:
        search_criteria = "FLAGGED" if only_flagged else "ALL"
        try:
            typ, data = conn.uid("search", None, search_criteria)
            if typ != "OK":
                raise ImapConnectionError(f"Could not search {folder!r}.")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not search {folder!r} - {e}") from e

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
            is_flagged = bool(flags_match and b"\\Flagged" in flags_match.group(1))
            summaries.append(parse_envelope_row(raw_uid.decode(), header_bytes, is_seen, is_flagged))

        return summaries


def get_message(host: str, port: int, username: str, password: str, uid: str, folder: str = "INBOX") -> MessageDetail:
    """Fetch and parse one full message by UID. This is a real (non-PEEK)
    fetch - opening a message correctly marks it \\Seen, unlike listing."""
    with imap_connection(host, port, username, password, folder=folder) as conn:
        try:
            typ, fetch_data = conn.uid("fetch", uid, "(RFC822)")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not fetch message {uid!r} - {e}") from e

        if typ != "OK" or not fetch_data or fetch_data[0] is None:
            raise ImapError(f"Message {uid!r} not found.")

        _, raw_bytes = fetch_data[0]
        return parse_full_message(uid, raw_bytes)


def set_message_flags(
    host: str, port: int, username: str, password: str, uid: str, folder: str = "INBOX",
    is_starred: bool | None = None, is_read: bool | None = None,
) -> None:
    """Set/unset \\Flagged (star) and/or \\Seen (read) on one message.
    Passing None for either leaves that flag untouched - lets a caller
    change just one without needing to know the other's current value."""
    with imap_connection(host, port, username, password, folder=folder) as conn:
        if is_starred is not None:
            store_cmd = "+FLAGS" if is_starred else "-FLAGS"
            try:
                typ, _ = conn.uid("store", uid, store_cmd, "(\\Flagged)")
                if typ != "OK":
                    raise ImapError(f"Could not update star on message {uid!r}.")
            except imaplib.IMAP4.error as e:
                raise ImapConnectionError(f"Could not update star on message {uid!r} - {e}") from e

        if is_read is not None:
            store_cmd = "+FLAGS" if is_read else "-FLAGS"
            try:
                typ, _ = conn.uid("store", uid, store_cmd, "(\\Seen)")
                if typ != "OK":
                    raise ImapError(f"Could not update read status on message {uid!r}.")
            except imaplib.IMAP4.error as e:
                raise ImapConnectionError(f"Could not update read status on message {uid!r} - {e}") from e


def _copy_flag_expunge(conn: imaplib.IMAP4, uid: str, destination: str) -> None:
    """Portable move primitive: COPY to destination, mark \\Deleted, EXPUNGE
    the currently selected folder. Standard IMAP has no universally
    supported atomic MOVE (RFC 6851 is an extension, not guaranteed
    present), so this three-step sequence is the portable equivalent."""
    try:
        typ, _ = conn.uid("copy", uid, _quote_mailbox(destination))
        if typ != "OK":
            raise ImapError(f"Could not copy message {uid!r} to {destination!r}.")
    except imaplib.IMAP4.error as e:
        raise ImapConnectionError(f"Could not copy message {uid!r} to {destination!r} - {e}") from e

    try:
        typ, _ = conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
        if typ != "OK":
            raise ImapError(f"Could not mark message {uid!r} deleted.")
    except imaplib.IMAP4.error as e:
        raise ImapConnectionError(f"Could not mark message {uid!r} deleted - {e}") from e

    conn.expunge()


def archive_message(host: str, port: int, username: str, password: str, uid: str, source_folder: str = "INBOX") -> str:
    """Move a message to the mailbox's Archive-role folder (or Gmail's "All
    Mail", mapped to the same role). Raises NoArchiveFolderError if no such
    folder can be resolved - an explicit failure, not a silent no-op.
    Returns the resolved archive folder's real IMAP name."""
    with imap_connection(host, port, username, password, folder=None) as conn:
        archive = next((f for f in _list_folders_on_connection(conn) if f.role == "archive"), None)
        if archive is None:
            raise NoArchiveFolderError("No Archive folder found on this mailbox.")

        try:
            typ, _ = conn.select(_quote_mailbox(source_folder))
            if typ != "OK":
                raise ImapConnectionError(f"Could not open folder {source_folder!r}.")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not open folder {source_folder!r} - {e}") from e

        _copy_flag_expunge(conn, uid, archive.name)
        return archive.name


def delete_message(host: str, port: int, username: str, password: str, uid: str, source_folder: str = "INBOX") -> None:
    """Delete a message. Moves to Trash by default (reversible, matches
    standard webmail UX); if source_folder IS the Trash-role folder, or no
    Trash-role folder exists anywhere on this mailbox, deletes permanently
    in place instead (STORE \\Deleted + EXPUNGE, no copy)."""
    with imap_connection(host, port, username, password, folder=None) as conn:
        folders = _list_folders_on_connection(conn)
        source_role = next((f.role for f in folders if f.name == source_folder), None)
        trash = next((f for f in folders if f.role == "trash"), None)

        try:
            typ, _ = conn.select(_quote_mailbox(source_folder))
            if typ != "OK":
                raise ImapConnectionError(f"Could not open folder {source_folder!r}.")
        except imaplib.IMAP4.error as e:
            raise ImapConnectionError(f"Could not open folder {source_folder!r} - {e}") from e

        if source_role == "trash" or trash is None:
            try:
                typ, _ = conn.uid("store", uid, "+FLAGS", "(\\Deleted)")
                if typ != "OK":
                    raise ImapError(f"Could not mark message {uid!r} deleted.")
            except imaplib.IMAP4.error as e:
                raise ImapConnectionError(f"Could not mark message {uid!r} deleted - {e}") from e
            conn.expunge()
        else:
            _copy_flag_expunge(conn, uid, trash.name)
