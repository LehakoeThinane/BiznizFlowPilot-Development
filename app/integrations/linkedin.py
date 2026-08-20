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

from app.core.config import settings


def poll_new_leads() -> list[dict]:
    """Fetch new Lead Gen Form submissions since the last poll.

    Returns an empty list until this integration is actually implemented
    against a real, approved LinkedIn Lead Sync API credential.
    """
    return []


class LinkedInPostError(Exception):
    """Raised when a configured LinkedIn company-page post attempt fails."""


def post_company_update(text: str, article_url: str) -> str | None:
    """Share a company-page update linking to a published blog article.

    Same reasoning as poll_new_leads() above, applied to a different
    LinkedIn product: posting to an Organization Page requires the
    Community Management API product and the w_organization_social scope,
    which needs LinkedIn's own app-review approval - not guaranteed
    self-serve, and not worth guessing at an unverified request shape.

    Returns None (a quiet no-op, not an error) while
    linkedin_organization_access_token/linkedin_organization_urn are
    unset - callers should treat that as "not configured yet", exactly
    like every other empty-means-disabled integration in this codebase.

    Once real, approved credentials exist, implement the actual HTTP call
    here against LinkedIn's confirmed current API shape - every caller of
    this function already handles both the None and the exception case,
    so nothing else needs to change.
    """
    if not (settings.linkedin_organization_access_token and settings.linkedin_organization_urn):
        return None

    raise LinkedInPostError(
        "LinkedIn organization credentials are set, but post_company_update() "
        "hasn't been implemented against a verified API shape yet - see this "
        "function's docstring in app/integrations/linkedin.py."
    )
