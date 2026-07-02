"""Admin API — cross-tenant endpoints for superadmin users only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.business import Business
from app.models.event import Event
from app.models.user import User
from app.models.workflow import WorkflowRun
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/admin/v1", tags=["admin"])


# ── Superadmin guard ─────────────────────────────────────────────────────────

def get_superadmin(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Dependency that restricts access to users with role='superadmin'."""
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return current_user


# ── Response schemas ──────────────────────────────────────────────────────────

class TenantSummary(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None
    user_count: int
    created_at: str

    model_config = {"from_attributes": True}


class TenantDetail(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None
    created_at: str
    users: list[dict]
    counts: dict


class UserAdminView(BaseModel):
    id: str
    business_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str


class EventAdminView(BaseModel):
    id: str
    business_id: str
    actor_id: str | None
    event_type: str
    entity_type: str
    entity_id: str
    description: str | None
    status: str
    created_at: str


class WorkflowRunAdminView(BaseModel):
    id: str
    business_id: str
    status: str
    error_message: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str


class PlatformStats(BaseModel):
    total_tenants: int
    total_users: int
    active_users: int
    total_events: int
    total_workflow_runs: int
    workflow_runs_failed: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=PlatformStats)
def get_platform_stats(
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformStats:
    """Platform-wide aggregate counts."""
    total_tenants = db.query(func.count(Business.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    total_events = db.query(func.count(Event.id)).scalar() or 0
    total_runs = db.query(func.count(WorkflowRun.id)).scalar() or 0
    failed_runs = (
        db.query(func.count(WorkflowRun.id))
        .filter(WorkflowRun.status == "failed")
        .scalar()
        or 0
    )

    return PlatformStats(
        total_tenants=total_tenants,
        total_users=total_users,
        active_users=active_users,
        total_events=total_events,
        total_workflow_runs=total_runs,
        workflow_runs_failed=failed_runs,
    )


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[TenantSummary]:
    """List all tenants with their user counts."""
    rows = (
        db.query(Business, func.count(User.id).label("user_count"))
        .outerjoin(User, User.business_id == Business.id)
        .group_by(Business.id)
        .order_by(Business.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        TenantSummary(
            id=str(biz.id),
            name=biz.name,
            email=biz.email,
            phone=biz.phone,
            user_count=count,
            created_at=biz.created_at.isoformat(),
        )
        for biz, count in rows
    ]


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
def get_tenant(
    tenant_id: UUID,
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantDetail:
    """Single tenant deep view: users + entity counts."""
    biz = db.query(Business).filter(Business.id == tenant_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Tenant not found")

    users = db.query(User).filter(User.business_id == tenant_id).all()
    event_count = db.query(func.count(Event.id)).filter(Event.business_id == tenant_id).scalar() or 0
    run_count = db.query(func.count(WorkflowRun.id)).filter(WorkflowRun.business_id == tenant_id).scalar() or 0

    return TenantDetail(
        id=str(biz.id),
        name=biz.name,
        email=biz.email,
        phone=biz.phone,
        created_at=biz.created_at.isoformat(),
        users=[
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        counts={
            "users": len(users),
            "events": event_count,
            "workflow_runs": run_count,
        },
    )


@router.patch("/users/{user_id}", response_model=UserAdminView)
def toggle_user_active(
    user_id: UUID,
    is_active: bool,
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserAdminView:
    """Activate or deactivate any user across all tenants."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = is_active
    db.commit()
    db.refresh(user)

    return UserAdminView(
        id=str(user.id),
        business_id=str(user.business_id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
    )


@router.get("/events", response_model=list[EventAdminView])
def list_events(
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
    business_id: UUID | None = Query(None),
    event_type: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[EventAdminView]:
    """Cross-tenant audit log, optionally filtered by business or event type."""
    q = db.query(Event)
    if business_id:
        q = q.filter(Event.business_id == business_id)
    if event_type:
        q = q.filter(Event.event_type == event_type)

    rows = q.order_by(Event.created_at.desc()).offset(skip).limit(limit).all()

    return [
        EventAdminView(
            id=str(e.id),
            business_id=str(e.business_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            event_type=e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
            entity_type=e.entity_type,
            entity_id=str(e.entity_id),
            description=e.description,
            status=e.status.value if hasattr(e.status, "value") else str(e.status),
            created_at=e.created_at.isoformat(),
        )
        for e in rows
    ]


@router.get("/workflow-runs", response_model=list[WorkflowRunAdminView])
def list_workflow_runs(
    _: Annotated[CurrentUser, Depends(get_superadmin)],
    db: Annotated[Session, Depends(get_db)],
    business_id: UUID | None = Query(None),
    run_status: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[WorkflowRunAdminView]:
    """Cross-tenant workflow run list, optionally filtered by business or status."""
    q = db.query(WorkflowRun)
    if business_id:
        q = q.filter(WorkflowRun.business_id == business_id)
    if run_status:
        q = q.filter(WorkflowRun.status == run_status)

    rows = q.order_by(WorkflowRun.created_at.desc()).offset(skip).limit(limit).all()

    return [
        WorkflowRunAdminView(
            id=str(r.id),
            business_id=str(r.business_id),
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            error_message=r.error_message,
            started_at=r.started_at.isoformat() if r.started_at else None,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
