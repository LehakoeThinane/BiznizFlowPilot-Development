"""Platform admin API - cross-tenant endpoints for vendor staff only.

Replaces the old app/api/admin.py "superadmin" scaffold, which gated on an
unconstrained users.role string that could never legitimately be set to
"superadmin". Every route here is gated on get_current_platform_admin,
which validates against the fully separate platform_admins table/token type.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import EventType
from app.dependencies_platform import get_current_platform_admin, require_platform_role
from app.models.business import Business
from app.models.event import Event
from app.models.organization import Organization
from app.models.user import User
from app.models.workflow import WorkflowRun
from app.repositories.organization import OrganizationRepository
from app.schemas.platform import (
    CurrentPlatformAdmin,
    OrganizationAdminListResponse,
    OrganizationAdminResponse,
    OrganizationAdminUpdate,
    OrganizationEmailConfigResponse,
    OrganizationEmailConfigUpdate,
    OrganizationProvisionRequest,
    PlatformAdminCreate,
    PlatformAdminResponse,
)
from app.services.event import EventService
from app.services.invitation import InvitationService
from app.services.organization import OrganizationService
from app.services.platform_audit import record_audit
from app.services.platform_auth import PlatformAuthService

router = APIRouter(prefix="/platform/v1", tags=["platform-admin"])


# ── Response schemas (cross-tenant read views, unchanged from the old scaffold) ──

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


class UserPlatformListItem(BaseModel):
    id: str
    business_id: str
    business_name: str
    organization_id: str
    organization_name: str
    email: str
    full_name: str
    role: str
    is_active: bool
    plan_tier: str
    subscription_status: str
    created_at: str


class UserPlatformListResponse(BaseModel):
    total: int
    items: list[UserPlatformListItem]


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
    total_organizations: int
    total_tenants: int
    total_users: int
    active_users: int
    total_events: int
    total_workflow_runs: int
    workflow_runs_failed: int
    organizations_by_plan_tier: dict[str, int]
    mrr_zar: int
    trial_conversion_rate: float | None


# Illustrative MRR only - derived from the advertised prices on the pricing
# page (mmnexus.co.za/biznizflowpilot), not from real per-org billing
# records, since no billing system stores actual contract amounts yet.
# Enterprise is "Custom" pricing and excluded from the estimate.
PLAN_TIER_MONTHLY_PRICE_ZAR = {"starter": 8750, "professional": 35000}


# ── Stats / cross-tenant read endpoints ──────────────────────────────────────

@router.get("/stats", response_model=PlatformStats)
def get_platform_stats(
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformStats:
    """Platform-wide aggregate counts."""
    total_organizations = db.query(func.count(Organization.id)).scalar() or 0
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

    org_repo = OrganizationRepository(db)
    tier_counts = org_repo.count_by_plan_tier()
    mrr_zar = sum(tier_counts.get(tier, 0) * price for tier, price in PLAN_TIER_MONTHLY_PRICE_ZAR.items())

    # A trial "cohort" is any org that was ever provisioned as a trial -
    # trial_ends_at is only ever set at trial creation (see
    # OrganizationService.create_organization_shell), so it survives as a
    # marker even after plan_tier is later changed to a paid tier.
    trial_cohort_size = org_repo.count_trial_cohort()
    converted_count = org_repo.count_converted_from_trial()
    trial_conversion_rate = (converted_count / trial_cohort_size) if trial_cohort_size else None

    return PlatformStats(
        total_organizations=total_organizations,
        total_tenants=total_tenants,
        total_users=total_users,
        active_users=active_users,
        total_events=total_events,
        total_workflow_runs=total_runs,
        workflow_runs_failed=failed_runs,
        organizations_by_plan_tier=tier_counts,
        mrr_zar=mrr_zar,
        trial_conversion_rate=trial_conversion_rate,
    )


@router.get("/tenants", response_model=list[TenantSummary])
def list_tenants(
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[TenantSummary]:
    """List all subsidiaries (tenants) with their user counts."""
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
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
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


@router.get("/users", response_model=UserPlatformListResponse)
def list_users(
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> UserPlatformListResponse:
    """Flat, cross-tenant list of every user - who they are, which company
    they belong to, and whether that company is on a trial or a paid plan.
    Same three-table join _org_to_admin_response already does per-org,
    just flattened to one row per user instead of one row per org."""
    total = db.query(func.count(User.id)).scalar() or 0

    rows = (
        db.query(User, Business, Organization)
        .join(Business, Business.id == User.business_id)
        .join(Organization, Organization.id == Business.organization_id)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return UserPlatformListResponse(
        total=total,
        items=[
            UserPlatformListItem(
                id=str(user.id),
                business_id=str(business.id),
                business_name=business.name,
                organization_id=str(org.id),
                organization_name=org.name,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                plan_tier=org.plan_tier,
                subscription_status=org.subscription_status,
                created_at=user.created_at.isoformat(),
            )
            for user, business, org in rows
        ],
    )


@router.patch("/users/{user_id}", response_model=UserAdminView)
def toggle_user_active(
    user_id: UUID,
    is_active: bool,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserAdminView:
    """Activate or deactivate any user across all tenants."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = is_active
    record_audit(
        db,
        current_admin.platform_admin_id,
        "user.toggle_active",
        target_type="user",
        target_id=user.id,
        meta_data={"is_active": is_active},
    )
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
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
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
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
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


# ── Organization provisioning ────────────────────────────────────────────────

def _org_to_admin_response(db: Session, org: Organization) -> OrganizationAdminResponse:
    subsidiary_count = (
        db.query(func.count(Business.id)).filter(Business.organization_id == org.id).scalar() or 0
    )
    user_count = (
        db.query(func.count(User.id))
        .join(Business, Business.id == User.business_id)
        .filter(Business.organization_id == org.id)
        .scalar()
        or 0
    )
    return OrganizationAdminResponse(
        id=org.id,
        name=org.name,
        billing_email=org.billing_email,
        plan_tier=org.plan_tier,
        subscription_status=org.subscription_status,
        seats_included=org.seats_included,
        subsidiary_count=subsidiary_count,
        user_count=user_count,
    )


@router.get("/organizations", response_model=OrganizationAdminListResponse)
def list_organizations(
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> OrganizationAdminListResponse:
    """List all client organizations."""
    org_repo = OrganizationRepository(db)
    orgs = org_repo.list_all(skip=skip, limit=limit)
    return OrganizationAdminListResponse(
        total=org_repo.count(),
        items=[_org_to_admin_response(db, org) for org in orgs],
    )


@router.post("/organizations", response_model=OrganizationAdminResponse, status_code=status.HTTP_201_CREATED)
def provision_organization(
    body: OrganizationProvisionRequest,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationAdminResponse:
    """Provision a brand-new client Organization + first subsidiary, then invite the owner.

    No owner User is created here — ownership transfers to the client via the
    same invite-token flow used for tenant-side invites (InvitationService),
    so the platform admin never sets or knows the client's password.
    """
    org_service = OrganizationService(db)
    try:
        shell = org_service.create_organization_shell(
            org_name=body.org_name,
            billing_email=body.billing_email,
            subsidiary_name=body.subsidiary_name,
            primary_domain=body.primary_domain,
            plan_tier=body.plan_tier,
        )
        invitation, raw_token = InvitationService(db).create_invitation(
            business_id=shell.business.id,
            organization_id=shell.organization.id,
            email=body.owner_email,
            role="owner",
            invited_by=None,
            inviter_role="platform_admin",
            inviter_name=f"{current_admin.full_name} (Platform Team)",
        )
    except ValueError as e:
        db.rollback()
        record_audit(
            db,
            current_admin.platform_admin_id,
            "organization.provision",
            result="failed",
            meta_data={"reason": str(e), "org_name": body.org_name},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    from app.services.email import send_invite_email  # local import - patchable in tests, matches app/api/invites.py

    try:
        send_invite_email(
            to_email=body.owner_email,
            organization_name=shell.organization.name,
            business_name=shell.business.name,
            invited_by_name=f"{current_admin.full_name} (Platform Team)",
            raw_token=raw_token,
        )
    except Exception:
        pass  # email delivery failure is logged inside send_invite_email

    record_audit(
        db,
        current_admin.platform_admin_id,
        "organization.provision",
        target_type="organization",
        target_id=shell.organization.id,
        meta_data={"org_name": body.org_name, "owner_email": body.owner_email, "invitation_id": str(invitation.id)},
    )

    EventService(db).create_event(
        business_id=shell.business.id,
        event_type=EventType.ORGANIZATION_PROVISIONED,
        entity_type="organization",
        entity_id=shell.organization.id,
        description=f"Organization '{shell.organization.name}' provisioned by platform admin; owner invited",
        commit=False,
    )

    db.commit()
    db.refresh(shell.organization)
    return _org_to_admin_response(db, shell.organization)


@router.get("/organizations/{organization_id}", response_model=OrganizationAdminResponse)
def get_organization(
    organization_id: UUID,
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationAdminResponse:
    """Get a single organization's detail."""
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _org_to_admin_response(db, org)


@router.patch("/organizations/{organization_id}", response_model=OrganizationAdminResponse)
def update_organization(
    organization_id: UUID,
    body: OrganizationAdminUpdate,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationAdminResponse:
    """Update an organization's billing/plan fields - platform admin only.

    Tenant IT Admins can rename their own org (PATCH /api/v1/org), but only
    platform admins can touch plan_tier/subscription_status/seats_included.
    """
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    updated_fields = []
    if body.name is not None:
        org.name = body.name
        updated_fields.append("name")
    if body.plan_tier is not None:
        org.plan_tier = body.plan_tier
        updated_fields.append("plan_tier")
    if body.subscription_status is not None:
        org.subscription_status = body.subscription_status
        updated_fields.append("subscription_status")
    if body.seats_included is not None:
        org.seats_included = body.seats_included
        updated_fields.append("seats_included")

    record_audit(
        db,
        current_admin.platform_admin_id,
        "organization.update",
        target_type="organization",
        target_id=org.id,
        meta_data={"updated_fields": updated_fields},
    )

    primary_business = (
        db.query(Business)
        .filter(Business.organization_id == org.id, Business.is_primary_subsidiary.is_(True))
        .first()
    )
    if primary_business:
        EventService(db).create_event(
            business_id=primary_business.id,
            event_type=EventType.ORGANIZATION_UPDATED,
            entity_type="organization",
            entity_id=org.id,
            description=f"Organization '{org.name}' updated by platform admin",
            data={"updated_fields": updated_fields},
            commit=False,
        )

    db.commit()
    db.refresh(org)

    return _org_to_admin_response(db, org)


def _org_to_email_config_response(org: Organization) -> OrganizationEmailConfigResponse:
    return OrganizationEmailConfigResponse(
        smtp_host=org.smtp_host,
        smtp_port=org.smtp_port,
        smtp_username=org.smtp_username,
        smtp_password_set=bool(org.smtp_password_encrypted),
        smtp_from_email=org.smtp_from_email,
        smtp_from_name=org.smtp_from_name,
    )


@router.get("/organizations/{organization_id}/email-config", response_model=OrganizationEmailConfigResponse)
def get_organization_email_config(
    organization_id: UUID,
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationEmailConfigResponse:
    """View an organization's custom SMTP sender config - the password itself is never returned."""
    org = OrganizationRepository(db).get_by_id(organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return _org_to_email_config_response(org)


@router.put("/organizations/{organization_id}/email-config", response_model=OrganizationEmailConfigResponse)
def set_organization_email_config(
    organization_id: UUID,
    body: OrganizationEmailConfigUpdate,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(require_platform_role("admin", "super_admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationEmailConfigResponse:
    """Set/replace an organization's custom SMTP sender - so its meeting
    invites (and future business emails) come from the business's own
    domain instead of the platform default. Requires admin/super_admin."""
    service = OrganizationService(db)
    org = service.set_email_config(
        organization_id,
        smtp_host=body.smtp_host,
        smtp_port=body.smtp_port,
        smtp_username=body.smtp_username,
        smtp_password=body.smtp_password,
        smtp_from_email=body.smtp_from_email,
        smtp_from_name=body.smtp_from_name,
    )
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    record_audit(
        db,
        current_admin.platform_admin_id,
        "organization.email_config_updated",
        target_type="organization",
        target_id=org.id,
        # Never include the password itself in the audit trail.
        meta_data={"smtp_host": body.smtp_host, "smtp_from_email": body.smtp_from_email},
    )

    db.commit()
    db.refresh(org)
    return _org_to_email_config_response(org)


@router.delete("/organizations/{organization_id}/email-config", status_code=status.HTTP_204_NO_CONTENT)
def clear_organization_email_config(
    organization_id: UUID,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(require_platform_role("admin", "super_admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Revert an organization to the platform-default email sender."""
    service = OrganizationService(db)
    org = service.clear_email_config(organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    record_audit(
        db,
        current_admin.platform_admin_id,
        "organization.email_config_cleared",
        target_type="organization",
        target_id=org.id,
    )
    db.commit()


# ── Platform admin management ────────────────────────────────────────────────

@router.get("/admins/me", response_model=PlatformAdminResponse)
def get_my_platform_admin(
    current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdminResponse:
    """Return the current platform admin's own profile."""
    from app.models.platform_admin import PlatformAdmin

    admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == current_admin.platform_admin_id).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return PlatformAdminResponse(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        platform_role=admin.platform_role,
        is_active=admin.is_active,
        impersonation_allowed=admin.impersonation_allowed,
        last_login_at=admin.last_login_at.isoformat() if admin.last_login_at else None,
    )


@router.post("/admins/me/change-password", response_model=dict)
def change_my_platform_admin_password(
    current_admin: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
    current_password: str = Body(...),
    new_password: str = Body(...),
) -> dict:
    """Change the current platform admin's own password."""
    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")
    try:
        PlatformAuthService(db).change_password(
            current_admin.platform_admin_id, current_password, new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"message": "Password changed successfully"}


@router.post("/admins", response_model=PlatformAdminResponse, status_code=status.HTTP_201_CREATED)
def create_platform_admin(
    body: PlatformAdminCreate,
    current_admin: Annotated[CurrentPlatformAdmin, Depends(require_platform_role("admin", "super_admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformAdminResponse:
    """Create a new platform admin - requires an existing admin or super_admin."""
    service = PlatformAuthService(db)
    try:
        admin = service.create_admin(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            platform_role=body.platform_role,
            impersonation_allowed=body.impersonation_allowed,
            created_by_id=current_admin.platform_admin_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return PlatformAdminResponse(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        platform_role=admin.platform_role,
        is_active=admin.is_active,
        impersonation_allowed=admin.impersonation_allowed,
        last_login_at=None,
    )
