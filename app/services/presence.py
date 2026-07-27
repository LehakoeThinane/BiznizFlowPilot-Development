"""Presence computation - online/offline is always derived, never stored.

A user's chosen `status` (online/away/busy/in_meeting/custom) persists on
User indefinitely, independent of whether they're actually connected right
now. Whether that status is currently shown, or overridden to "offline", is
decided here at read time from last_seen_at staleness - so a user who set
"Busy" and closed their laptop reappears as "Busy" (not reset to "online")
the moment their heartbeat resumes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.user import User
from app.schemas.user import PresenceOut

PRESENCE_STALE_AFTER_SECONDS = 120
"""2x the 60s client heartbeat interval - tolerates one missed beat before
treating a user as offline."""


def compute_presence(user: User) -> PresenceOut:
    last_seen = user.last_seen_at
    is_online = last_seen is not None and (
        datetime.now(timezone.utc) - _as_utc(last_seen)
    ).total_seconds() <= PRESENCE_STALE_AFTER_SECONDS

    if not is_online:
        return PresenceOut(status="offline", status_text=None, last_seen_at=last_seen, is_online=False)

    return PresenceOut(status=user.status, status_text=user.status_text, last_seen_at=last_seen, is_online=True)


def offline_presence() -> PresenceOut:
    """Presence for a user record we don't have (e.g. a deleted participant)."""
    return PresenceOut(status="offline", status_text=None, last_seen_at=None, is_online=False)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
