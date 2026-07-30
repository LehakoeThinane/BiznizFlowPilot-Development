"""Plan-tier feature gating.

Mirrors app/core/permissions.py's shape (role-based guards) but gates on
Organization.plan_tier instead of User.role. "legacy" (pre-existing accounts,
backfilled by migration 20260702_03) gets unrestricted access permanently.
"trial" (manually-onboarded accounts pending a plan) gets unrestricted
access only until Organization.trial_ends_at passes - once expired, a
trial account loses access to everything, not just the gated premium
features, since there is no paid tier underneath it to fall back to.
Only starter/professional/enterprise (real self-serve subscriptions) are
feature-gated; legacy and an active trial are exempt from FEATURE_TIERS.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.organization import Organization
from app.repositories.organization import OrganizationRepository
from app.schemas.auth import CurrentUser

FULL_ACCESS_TIERS = frozenset({"legacy", "trial", "enterprise"})

FEATURE_TIERS: dict[str, frozenset[str]] = {
    "hr": frozenset({"enterprise"}),
    "multi_subsidiary": frozenset({"enterprise"}),
    "finance": frozenset({"growth", "professional", "enterprise"}),
    "sales_orders": frozenset({"growth", "professional", "enterprise"}),
    "purchase_orders": frozenset({"growth", "professional", "enterprise"}),
    "meetings": frozenset({"growth", "professional", "enterprise"}),
    "messaging": frozenset({"growth", "professional", "enterprise"}),
    "email": frozenset({"growth", "professional", "enterprise"}),
    "ai_chat": frozenset({"growth", "professional", "enterprise"}),
    "workflow_automation": frozenset({"growth", "professional", "enterprise"}),
    "document_authoring": frozenset({"growth", "professional", "enterprise"}),
    "customer_portal": frozenset({"growth", "professional", "enterprise"}),
}

SEAT_LIMITS: dict[str, int | None] = {
    "starter": 15, "growth": 25, "professional": 100, "enterprise": None,
}
LOCATION_LIMITS: dict[str, int | None] = {
    "starter": 1, "growth": 3, "professional": None, "enterprise": None,
}


def _trial_expired(org: Organization) -> bool:
    """Whether a trial-tier org's trial window has passed. Not applicable to
    (always False for) any other tier - callers should only consult this
    when org.plan_tier == 'trial'.

    trial_ends_at is always written as UTC (see OrganizationService), but
    SQLite (used in tests) silently drops tzinfo on round-trip unlike
    Postgres - normalize a naive value back to UTC rather than let the
    comparison below raise.
    """
    ends_at = org.trial_ends_at
    if ends_at is None:
        return False
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    return ends_at < datetime.now(timezone.utc)


def _has_full_access(org: Organization) -> bool:
    if org.plan_tier not in FULL_ACCESS_TIERS:
        return False
    if org.plan_tier == "trial" and _trial_expired(org):
        return False
    return True


def _resolve_org(current_user: CurrentUser, db: Session) -> Organization:
    org = (
        OrganizationRepository(db).get_by_id(current_user.organization_id)
        if current_user.organization_id
        else None
    )
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization on this account - cannot verify plan access.",
        )
    return org


def require_feature(feature: str):
    """FastAPI dependency factory: 403s unless the org's plan_tier includes `feature`.

    Fails closed - an org that can't be resolved (including a CurrentUser
    with no organization_id at all) is denied, not granted the legacy-tier
    fallback, since a data-integrity gap is not the same thing as a
    grandfathered account.
    """

    def _dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> CurrentUser:
        org = _resolve_org(current_user, db)
        if _has_full_access(org) or org.plan_tier in FEATURE_TIERS.get(feature, frozenset()):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Upgrade your plan to use {feature.replace('_', ' ')}.",
        )

    return _dependency


def require_active_trial(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentUser:
    """FastAPI dependency: 403s only for an expired trial - a no-op for every
    other tier (starter/professional/enterprise/legacy keep whatever
    require_feature already allows them). Applied broadly (via
    app.include_router(..., dependencies=[...]) in main.py) to every
    tenant-data router, since an expired trial has no paid tier to fall
    back to and should lose access to everything, not just the features
    that require_feature already gates for paying tiers.
    """
    org = _resolve_org(current_user, db)
    if org.plan_tier == "trial" and _trial_expired(org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your trial has ended. Upgrade your plan to continue.",
        )
    return current_user
