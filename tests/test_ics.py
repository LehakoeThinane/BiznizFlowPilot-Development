"""Tests for app/utils/ics.py - the hand-rolled single-VEVENT .ics builder."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.utils.ics import build_meeting_ics


def _build(**overrides):
    defaults = dict(
        meeting_id=uuid4(),
        title="Weekly sync",
        description=None,
        start_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 10, 30, tzinfo=timezone.utc),
        organizer_email="owner@example.com",
        organizer_name="Owner",
        attendee_email="guest@example.com",
        sequence=0,
        method="REQUEST",
    )
    defaults.update(overrides)
    return build_meeting_ics(**defaults).decode("utf-8")


def test_basic_structure():
    ics = _build()
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip("\r\n").endswith("END:VCALENDAR")
    assert "BEGIN:VEVENT\r\n" in ics
    assert "END:VEVENT\r\n" in ics
    assert "METHOD:REQUEST\r\n" in ics


def test_line_folding_at_75_octets():
    long_title = "A" * 200
    ics = _build(title=long_title)
    for line in ics.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, f"unfolded line: {line!r}"
    # Folded continuation lines start with a single space.
    lines = ics.split("\r\n")
    summary_idx = next(i for i, l in enumerate(lines) if l.startswith("SUMMARY:"))
    assert lines[summary_idx + 1].startswith(" ")


def test_text_escaping():
    ics = _build(description="Line1\nLine2, with; special\\chars")
    assert "DESCRIPTION:Line1\\nLine2\\, with\\; special\\\\chars" in ics


def test_sequence_increments_between_calls():
    first = _build(sequence=0)
    second = _build(sequence=1)
    assert "SEQUENCE:0\r\n" in first
    assert "SEQUENCE:1\r\n" in second


def test_uid_stable_for_same_meeting_id():
    mid = uuid4()
    first = _build(meeting_id=mid, sequence=0)
    second = _build(meeting_id=mid, sequence=1, title="Rescheduled")
    uid_line = next(l for l in first.split("\r\n") if l.startswith("UID:"))
    assert uid_line in second


def test_cancel_method_sets_status_cancelled():
    ics = _build(method="CANCEL")
    assert "METHOD:CANCEL\r\n" in ics
    assert "STATUS:CANCELLED\r\n" in ics


def test_request_method_sets_status_confirmed():
    ics = _build(method="REQUEST")
    assert "METHOD:REQUEST\r\n" in ics
    assert "STATUS:CONFIRMED\r\n" in ics


def test_no_description_omits_description_line():
    ics = _build(description=None)
    assert "DESCRIPTION" not in ics
