"""Plan-tier feature gating.

Mirrors app/core/permissions.py's shape (role-based guards) but gates on
Organization.plan_tier instead of User.role. "legacy" (pre-existing accounts,
backfilled by migration 20260702_03) and "trial" (manually-onboarded accounts
pending a plan) both get unrestricted access - legacy is grandfathered
permanently, trial gets full access for the trial window so prospects see
the value of the tier they'd actually buy. Only starter/professional/
enterprise (real self-serve Stripe subscriptions) are gated.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.organization import Organization
from app.schemas.auth import CurrentUser

FULL_ACCESS_TIERS = frozenset({"legacy", "trial", "enterprise"})

FEATURE_TIERS: dict[str, frozenset[str]] = {
    "hr": frozenset({"enterprise"}),
    "multi_subsidiary": frozenset({"enterprise"}),
    "finance": frozenset({"professional", "enterprise"}),
    "sales_orders": frozenset({"professional", "enterprise"}),
    "purchase_orders": frozenset({"professional", "enterprise"}),
    "meetings": frozenset({"professional", "enterprise"}),
    "messaging": frozenset({"professional", "enterprise"}),
    "ai_chat": frozenset({"professional", "enterprise"}),
    "workflow_automation": frozenset({"professional", "enterprise"}),
}

SEAT_LIMITS: dict[str, int | None] = {"starter": 50, "professional": 100, "enterprise": None}
LOCATION_LIMITS: dict[str, int | None] = {"starter": 1, "professional": None, "enterprise": None}


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
        org = (
            db.query(Organization).filter(Organization.id == current_user.organization_id).first()
            if current_user.organization_id
            else None
        )
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organization on this account - cannot verify plan access.",
            )
        if org.plan_tier in FULL_ACCESS_TIERS or org.plan_tier in FEATURE_TIERS.get(feature, frozenset()):
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Upgrade your plan to use {feature.replace('_', ' ')}.",
        )

    return _dependency
