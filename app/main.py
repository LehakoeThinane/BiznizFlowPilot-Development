"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
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
    events,
    finance,
    hr,
    invites,
    inventory,
    invoice,
    leads,
    meetings,
    messaging,
    metrics,
    notification,
    organizations,
    platform_admin,
    platform_auth,
    products,
    purchase_orders,
    sales_orders,
    search,
    suppliers,
    tasks,
    users,
    workflow_definitions,
    workflows,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.enums import EventType
from app.core.exception_handlers import unhandled_exception_handler
from app.core.security import hash_password, verify_password
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.services.event import EventService
from app.utils.logger import get_logger

limiter = Limiter(key_func=get_remote_address)

logger = get_logger(__name__)

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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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


@app.get("/health")
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

# Billing routes (no auth required — see app/api/billing.py docstring)
app.include_router(billing.router)

# CRM routes (auth required)
app.include_router(customers.router)
app.include_router(events.router)
app.include_router(leads.router)
app.include_router(tasks.router)
app.include_router(users.router)
app.include_router(invites.router)

# Meetings / calendar calls (auth required)
app.include_router(meetings.router)

# Direct messaging (auth required)
app.include_router(messaging.router)

# Organization / subsidiary management (auth required, IT Admin for mutations)
app.include_router(organizations.router)

# Automation routes (auth required)
app.include_router(workflows.router)
app.include_router(workflow_definitions.router)
app.include_router(metrics.router)
app.include_router(dashboard.router)

# ERP routes (auth required)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(inventory.router)
app.include_router(sales_orders.router)
app.include_router(purchase_orders.router)

# Finance, HR, Invoicing, Notifications (auth required)
app.include_router(finance.router)
app.include_router(hr.router)
app.include_router(invoice.router)
app.include_router(notification.router)

# AI chat routes (auth required)
app.include_router(chat.router)

# Global search (auth required)
app.include_router(search.router)

# Platform (vendor staff) routes — fully separate auth boundary, cross-tenant
app.include_router(platform_auth.router)
app.include_router(platform_admin.router)


# ============================================================================
# Protected Example Route (Requires auth)
# ============================================================================


def _serialize_current_user(current_user: CurrentUser) -> dict:
    """Normalize authenticated user response payload."""
    return {
        "user_id": current_user.user_id,
        "business_id": current_user.business_id,
        "email": current_user.email,
        "role": current_user.role,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
    }


@app.get(f"{settings.api_v1_prefix}/me")
def get_current_user_info(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    """Get current authenticated user information.
    
    Protected route - requires valid JWT token.
    """
    return _serialize_current_user(current_user)


@app.get(f"{settings.api_v1_prefix}/users/me")
def get_current_user_info_compat(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    """Compatibility alias for deployments using /api/v1/users/me."""
    return _serialize_current_user(current_user)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
