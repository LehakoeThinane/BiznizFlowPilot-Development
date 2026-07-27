"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import (
    auth,
    billing,
    chat,
    customers,
    dashboard,
    document_share,
    documents,
    events,
    finance,
    folders,
    hr,
    invites,
    inventory,
    invoice,
    leads,
    marketing_leads,
    meeting_rsvp,
    meetings,
    messaging,
    metrics,
    notification,
    onboarding,
    organizations,
    platform_admin,
    platform_auth,
    products,
    purchase_orders,
    purchase_requisitions,
    sales_orders,
    search,
    signup,
    suppliers,
    tasks,
    user_email,
    users,
    workflow_definitions,
    workflows,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.entitlements import require_active_trial
from app.core.enums import EventType
from app.core.exception_handlers import rate_limit_exceeded_handler, unhandled_exception_handler
from app.core.security import hash_password, verify_password
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.user import PresenceOut, StatusUpdateRequest
from app.services.event import EventService
from app.utils.logger import get_logger

limiter = Limiter(key_func=get_remote_address)

logger = get_logger(__name__)

# Error tracking - no-op unless SENTRY_DSN is set, so local/dev runs need no
# Sentry account at all.
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.version,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# ============================================================================
# Initialize FastAPI App
# ============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan hooks."""
    logger.info("Starting %s v%s", settings.app_name, settings.version)
    logger.info("Environment: %s", settings.environment)
    logger.info("Debug mode: %s", settings.debug)
    yield
    logger.info("Shutting down %s", settings.app_name)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ============================================================================
# Routes
# ============================================================================

# Health check (no auth required)
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect root path to API documentation."""
    return RedirectResponse(url="/docs")


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check(db: Session = Depends(get_db)) -> dict:
    """Health check endpoint — verifies DB connectivity for load balancer use."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database unreachable")

    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "database": db_ok,
    }


# Auth routes (no auth required)
app.include_router(auth.router, prefix=settings.api_v1_prefix)

# Free-trial signup routes (no auth required — see app/api/signup.py docstring)
app.include_router(signup.router, prefix=settings.api_v1_prefix)

# Billing routes (no auth required — see app/api/billing.py docstring)
app.include_router(billing.router)
app.include_router(document_share.public_router)

# Marketing-site gated guide downloads (no auth required — see app/api/marketing_leads.py docstring)
app.include_router(marketing_leads.router)

# Meeting RSVP (no auth required — see app/api/meeting_rsvp.py docstring)
app.include_router(meeting_rsvp.public_router)

# CRM routes (auth required)
# require_active_trial: a no-op for every tier except an expired trial,
# which loses access to everything (no paid tier to fall back to) rather
# than just the specific features require_feature gates for paying tiers.
# Not applied to auth/billing/organizations (see below) - those must stay
# reachable so an expired-trial account can still log in, read its own
# plan/trial status, and upgrade.
app.include_router(customers.router, dependencies=[Depends(require_active_trial)])
app.include_router(documents.router, dependencies=[Depends(require_active_trial)])
app.include_router(folders.router, dependencies=[Depends(require_active_trial)])
app.include_router(document_share.router, dependencies=[Depends(require_active_trial)])
app.include_router(events.router, dependencies=[Depends(require_active_trial)])
app.include_router(leads.router, dependencies=[Depends(require_active_trial)])
app.include_router(tasks.router, dependencies=[Depends(require_active_trial)])
app.include_router(users.router, dependencies=[Depends(require_active_trial)])
app.include_router(invites.router, dependencies=[Depends(require_active_trial)])

# Meetings / calendar calls (auth required)
app.include_router(meetings.router, dependencies=[Depends(require_active_trial)])

# Direct messaging (auth required)
app.include_router(messaging.router, dependencies=[Depends(require_active_trial)])

# Per-user email inbox (auth required, self-service)
app.include_router(user_email.router, dependencies=[Depends(require_active_trial)])

# Organization / subsidiary management (auth required, IT Admin for mutations)
# Deliberately NOT gated by require_active_trial - the frontend needs this
# reachable to read plan_tier/trial_ends_at and render the upgrade prompt.
app.include_router(organizations.router)

# Automation routes (auth required)
app.include_router(workflows.router, dependencies=[Depends(require_active_trial)])
app.include_router(workflow_definitions.router, dependencies=[Depends(require_active_trial)])
app.include_router(metrics.router, dependencies=[Depends(require_active_trial)])
app.include_router(dashboard.router, dependencies=[Depends(require_active_trial)])
app.include_router(onboarding.router, dependencies=[Depends(require_active_trial)])

# ERP routes (auth required)
app.include_router(products.router, dependencies=[Depends(require_active_trial)])
app.include_router(suppliers.router, dependencies=[Depends(require_active_trial)])
app.include_router(inventory.router, dependencies=[Depends(require_active_trial)])
app.include_router(sales_orders.router, dependencies=[Depends(require_active_trial)])
app.include_router(purchase_orders.router, dependencies=[Depends(require_active_trial)])
app.include_router(purchase_requisitions.router, dependencies=[Depends(require_active_trial)])

# Finance, HR, Invoicing, Notifications (auth required)
app.include_router(finance.router, dependencies=[Depends(require_active_trial)])
app.include_router(hr.router, dependencies=[Depends(require_active_trial)])
app.include_router(invoice.router, dependencies=[Depends(require_active_trial)])
app.include_router(notification.router, dependencies=[Depends(require_active_trial)])

# AI chat routes (auth required)
app.include_router(chat.router, dependencies=[Depends(require_active_trial)])

# Global search (auth required)
app.include_router(search.router, dependencies=[Depends(require_active_trial)])

# Platform (vendor staff) routes — fully separate auth boundary, cross-tenant
app.include_router(platform_auth.router)
app.include_router(platform_admin.router)


# ============================================================================
# Protected Example Route (Requires auth)
# ============================================================================


def _serialize_current_user(current_user: CurrentUser, db: Session) -> dict:
    """Normalize authenticated user response payload.

    Includes plan_tier/trial_ends_at so the frontend can show a trial-status
    banner - resolved via organization_id exactly like app/core/entitlements.py
    does, not stored on the JWT itself.

    Presence fields are flattened (status/status_text/last_seen_at/is_online)
    rather than nested, matching this endpoint's existing flat dict shape -
    UserResponse/OtherUser nest a `presence` object instead (see
    app/schemas/user.py's PresenceOut), this route just isn't a Pydantic model.
    """
    from app.repositories.organization import OrganizationRepository
    from app.services.presence import compute_presence

    plan_tier = None
    trial_ends_at = None
    if current_user.organization_id:
        org = OrganizationRepository(db).get_by_id(current_user.organization_id)
        if org:
            plan_tier = org.plan_tier
            trial_ends_at = org.trial_ends_at

    user = db.query(User).filter(User.id == current_user.user_id).first()
    presence = compute_presence(user) if user else None

    return {
        "user_id": current_user.user_id,
        "business_id": current_user.business_id,
        "email": current_user.email,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "plan_tier": plan_tier,
        "trial_ends_at": trial_ends_at,
        "status": presence.status if presence else None,
        "status_text": presence.status_text if presence else None,
        "last_seen_at": presence.last_seen_at if presence else None,
        "is_online": presence.is_online if presence else False,
    }


@app.get(f"{settings.api_v1_prefix}/me")
def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Get current authenticated user information.

    Protected route - requires valid JWT token.
    """
    return _serialize_current_user(current_user, db)


@app.get(f"{settings.api_v1_prefix}/users/me")
def get_current_user_info_compat(
    current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Compatibility alias for deployments using /api/v1/users/me."""
    return _serialize_current_user(current_user, db)


@app.patch(f"{settings.api_v1_prefix}/users/me")
def update_profile(
    first_name: str = Body(None),
    last_name: str = Body(None),
    avatar_url: str = Body(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Update the current user's display name and/or avatar."""
    from uuid import UUID as _UUID
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_fields = []
    if first_name is not None:
        user.first_name = first_name.strip()
        updated_fields.append("first_name")
    if last_name is not None:
        user.last_name = last_name.strip()
        updated_fields.append("last_name")
    if avatar_url is not None:
        user.avatar_url = avatar_url if avatar_url else None
        updated_fields.append("avatar_url")

    EventService(db).create_event(
        business_id=_UUID(str(current_user.business_id)),
        event_type=EventType.USER_PROFILE_UPDATED,
        entity_type="user",
        entity_id=_UUID(str(current_user.user_id)),
        actor_id=_UUID(str(current_user.user_id)),
        description=f"Profile updated for {user.full_name}",
        data={"updated_fields": updated_fields},
        commit=False,
    )

    db.commit()
    db.refresh(user)
    return {
        "user_id": str(user.id),
        "business_id": str(user.business_id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
    }


@app.post(f"{settings.api_v1_prefix}/users/me/change-password")
def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Change the current user's password."""
    from uuid import UUID as _UUID
    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(new_password)

    EventService(db).create_event(
        business_id=_UUID(str(current_user.business_id)),
        event_type=EventType.USER_PASSWORD_CHANGED,
        entity_type="user",
        entity_id=_UUID(str(current_user.user_id)),
        actor_id=_UUID(str(current_user.user_id)),
        description=f"Password changed for {user.full_name}",
        commit=False,
    )

    db.commit()
    return {"message": "Password changed successfully"}


@app.patch(f"{settings.api_v1_prefix}/users/me/status")
def update_status(
    payload: StatusUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresenceOut:
    """Set (or clear, via a preset) the current user's presence status.

    Also bumps last_seen_at - choosing a status is itself proof of activity,
    so there's no reason to make the user wait for the next heartbeat tick
    to show as online right after picking one.
    """
    from datetime import datetime, timezone

    from app.services.presence import compute_presence

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = payload.status
    user.status_text = payload.status_text
    user.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return compute_presence(user)


@app.post(f"{settings.api_v1_prefix}/users/me/heartbeat")
def heartbeat(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Keep-alive ping, fired every 60s while the app is open.

    No EventService entry, unlike update_profile/change_password - those are
    rare and user-initiated; this fires constantly for every active user and
    would flood the business activity feed if logged the same way.
    """
    from datetime import datetime, timezone

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
