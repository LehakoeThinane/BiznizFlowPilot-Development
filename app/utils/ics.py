"""Hand-rolled single-VEVENT .ics builder for meeting invites.

Deliberately not using a calendaring library (no icalendar/ics dependency):
the surface area needed is one non-recurring, UTC-timestamped VEVENT per
recipient - no recurrence rules, no VTIMEZONE blocks, no multi-component
calendars, which is where a library like `icalendar` actually earns its
keep. This matches the rest of the codebase's preference for hand-rolling
simple things (no template engine, inline f-string emails).

What a naive hand-roll gets wrong, and what this module gets right:
  - RFC 5545 line folding: any content line over 75 octets must be folded,
    continuation lines start with a single space, CRLF line endings
    throughout (not bare \\n).
  - TEXT escaping: backslash, semicolon, comma, and embedded newlines in
    SUMMARY/DESCRIPTION must be backslash-escaped.
  - A stable UID across the invite/update/cancel emails for the same
    meeting, so calendar clients correlate them into one event instead of
    creating duplicates.
  - SEQUENCE must be non-decreasing across re-sends of the same UID, or
    clients ignore the update - callers pass Meeting.version directly,
    since it already increments on every UPDATE.
  - METHOD:REQUEST for invite/update vs METHOD:CANCEL + STATUS:CANCELLED
    for cancellation - Outlook/Gmail treat these very differently.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

_CRLF = "\r\n"
_FOLD_LIMIT = 75


def _escape_text(value: str) -> str:
    """Escape TEXT-value special characters per RFC 5545 section 3.3.11."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold_line(line: str) -> str:
    """Fold a single content line so no physical line exceeds 75 octets.

    Continuation lines are prefixed with a single space, per RFC 5545
    section 3.1. Operates on UTF-8 byte length, not character count.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= _FOLD_LIMIT:
        return line

    chunks: list[str] = []
    remaining = line
    limit = _FOLD_LIMIT
    while remaining:
        # Fold on a byte boundary but never split a multi-byte UTF-8
        # character - trim back one character at a time if needed.
        chunk = remaining[:limit]
        while len(chunk.encode("utf-8")) > limit and chunk:
            chunk = chunk[:-1]
        chunks.append(chunk)
        remaining = remaining[len(chunk):]
        limit = _FOLD_LIMIT - 1  # continuation lines lose one column to the leading space
    return _CRLF.join([chunks[0]] + [" " + c for c in chunks[1:]])


def _dt_stamp(value: datetime) -> str:
    """Format a timezone-aware datetime as a UTC ICS DATE-TIME (...Z)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_meeting_ics(
    meeting_id: UUID,
    title: str,
    description: str | None,
    start_time: datetime,
    end_time: datetime,
    organizer_email: str,
    organizer_name: str,
    attendee_email: str,
    sequence: int,
    method: Literal["REQUEST", "CANCEL"] = "REQUEST",
) -> bytes:
    """Build a complete VCALENDAR/VEVENT .ics for one recipient.

    Returns fully folded, CRLF-terminated bytes ready to attach to an email.
    The UID is stable across calls for the same meeting_id, so invite,
    update, and cancel emails all correlate to one calendar entry.
    """
    uid = f"meeting-{meeting_id}@biznizflowpilot.com"
    now = _dt_stamp(datetime.now(timezone.utc))
    status = "CANCELLED" if method == "CANCEL" else "CONFIRMED"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BiznizFlowPilot//Meetings//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{now}",
        f"DTSTART:{_dt_stamp(start_time)}",
        f"DTEND:{_dt_stamp(end_time)}",
        f"SUMMARY:{_escape_text(title)}",
        f"ORGANIZER;CN={_escape_text(organizer_name)}:mailto:{organizer_email}",
        f"ATTENDEE;RSVP=TRUE;CN={_escape_text(attendee_email)}:mailto:{attendee_email}",
        f"STATUS:{status}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{_escape_text(description)}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    folded = [_fold_line(line) for line in lines]
    return (_CRLF.join(folded) + _CRLF).encode("utf-8")
