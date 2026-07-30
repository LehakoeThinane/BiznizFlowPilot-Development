"""LinkedIn Lead Sync API client - stubbed.

LinkedIn's Lead Sync API (the official way to pull native Lead Gen Form
submissions programmatically) has historically required a separate,
more restrictive partner-access tier beyond basic developer app access -
not guaranteed self-serve, and unverifiable without an actual approved
LinkedIn Developer app. This module is a structural placeholder: it
returns no leads until real credentials + a confirmed API shape exist.
Do not build a real HTTP call against undocumented specifics - update
this once app/core/config.py's linkedin_* settings are backed by an
actual approved app, and the real request/response shape is known.
"""

from __future__ import annotations


def poll_new_leads() -> list[dict]:
    """Fetch new Lead Gen Form submissions since the last poll.

    Returns an empty list until this integration is actually implemented
    against a real, approved LinkedIn Lead Sync API credential.
    """
    return []
