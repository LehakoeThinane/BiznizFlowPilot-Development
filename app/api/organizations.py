"""Organization and subsidiary management API - IT Admin's own-org scope."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.database import get_db
from app.dependencies import get_current_user, get_org_admin
from app.models.business import Business
from app.models.organization import Organization
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.schemas.auth import CurrentUser
from app.models.organization_domain import OrganizationDomain
from app.schemas.organization import (
    OrganizationDomainCreate,
    OrganizationDomainResponse,
    OrganizationResponse,
    OrganizationUpdate,
    SubsidiaryCreate,
    SubsidiaryListResponse,
    SubsidiaryResponse,
    SubsidiaryUpdate,
)
from app.services.event import EventService

router = APIRouter(prefix="/api/v1/org", tags=["organization"])


def _get_org_or_404(db: Session, organization_id: UUID) -> Organization:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def _require_same_org(current_user: CurrentUser, business: Business) -> None:
    """🧨 The one sanctioned place authorization checks organization_id instead
    of business_id - callers must always pair this with get_org_admin."""
    if str(business.organization_id) != str(current_user.organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business is not in your organization")


@router.get("", response_model=OrganizationResponse)
def get_organization(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    """Read-only organization summary - any authenticated user in the org."""
    org = _get_org_or_404(db, UUID(str(current_user.organization_id)))
    org_repo = OrganizationRepository(db)
    domains = [d.domain for d in org_repo.list_domains(org.id)]
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        plan_tier=org.plan_tier,
        subscription_status=org.subscription_status,
        domains=domains,
    )


@router.patch("", response_model=OrganizationResponse)
def update_organization(
    body: OrganizationUpdate,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    """Update organization settings - IT Admin only."""
    org = _get_org_or_404(db, UUID(str(current_user.organization_id)))
    if body.name is not None:
        org.name = body.name

    EventService(db).create_event(
        business_id=current_user.business_id,
        event_type=EventType.ORGANIZATION_UPDATED,
        entity_type="organization",
        entity_id=org.id,
        actor_id=current_user.user_id,
        description="Organization settings updated",
        commit=False,
    )

    db.commit()
    db.refresh(org)

    org_repo = OrganizationRepository(db)
    domains = [d.domain for d in org_repo.list_domains(org.id)]
    return OrganizationResponse(
        id=org.id, name=org.name, plan_tier=org.plan_tier,
        subscription_status=org.subscription_status, domains=domains,
    )


@router.get("/domains", response_model=list[OrganizationDomainResponse])
def list_domains(
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[OrganizationDomainResponse]:
    """List the organization's authorized email domains."""
    org_repo = OrganizationRepository(db)
    domains = org_repo.list_domains(UUID(str(current_user.organization_id)))
    return [OrganizationDomainResponse.model_validate(d) for d in domains]


@router.post("/domains", response_model=OrganizationDomainResponse, status_code=status.HTTP_201_CREATED)
def add_domain(
    body: OrganizationDomainCreate,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationDomainResponse:
    """Add an authorized email domain to the organization."""
    organization_id = UUID(str(current_user.organization_id))
    org_repo = OrganizationRepository(db)

    existing = (
        db.query(OrganizationDomain)
        .filter(OrganizationDomain.domain == body.domain.lower())
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This domain is already registered")

    if body.is_primary:
        db.query(OrganizationDomain).filter(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.is_primary.is_(True),
        ).update({"is_primary": False})

    domain = org_repo.add_domain(organization_id, body.domain, is_primary=body.is_primary)
    db.commit()
    db.refresh(domain)
    return OrganizationDomainResponse.model_validate(domain)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_domain(
    domain_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Remove an authorized email domain from the organization."""
    domain = (
        db.query(OrganizationDomain)
        .filter(
            OrganizationDomain.id == domain_id,
            OrganizationDomain.organization_id == UUID(str(current_user.organization_id)),
        )
        .first()
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    db.delete(domain)
    db.commit()


@router.get("/subsidiaries", response_model=SubsidiaryListResponse)
def list_subsidiaries(
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubsidiaryListResponse:
    """List all subsidiaries in the caller's organization."""
    rows = (
        db.query(Business, func.count(User.id).label("user_count"))
        .outerjoin(User, User.business_id == Business.id)
        .filter(Business.organization_id == UUID(str(current_user.organization_id)))
        .group_by(Business.id)
        .order_by(Business.created_at.asc())
        .all()
    )
    items = [
        SubsidiaryResponse(
            id=b.id, organization_id=b.organization_id, name=b.name, email=b.email,
            phone=b.phone, is_primary_subsidiary=b.is_primary_subsidiary,
            is_active=b.is_active, user_count=count,
        )
        for b, count in rows
    ]
    return SubsidiaryListResponse(total=len(items), items=items)


@router.post("/subsidiaries", response_model=SubsidiaryResponse, status_code=status.HTTP_201_CREATED)
def create_subsidiary(
    body: SubsidiaryCreate,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubsidiaryResponse:
    """Create a new subsidiary Business under the caller's organization."""
    organization_id = UUID(str(current_user.organization_id))

    existing = (
        db.query(Business)
        .filter(Business.organization_id == organization_id, Business.email == body.email)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A subsidiary with this email already exists in your organization",
        )

    business = Business(
        organization_id=organization_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        is_primary_subsidiary=False,
    )
    db.add(business)
    db.flush()

    EventService(db).create_event(
        business_id=business.id,
        event_type=EventType.SUBSIDIARY_CREATED,
        entity_type="business",
        entity_id=business.id,
        actor_id=current_user.user_id,
        description=f"Subsidiary '{business.name}' created",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    return SubsidiaryResponse(
        id=business.id, organization_id=business.organization_id, name=business.name,
        email=business.email, phone=business.phone,
        is_primary_subsidiary=business.is_primary_subsidiary, is_active=business.is_active,
        user_count=0,
    )


@router.get("/subsidiaries/{business_id}", response_model=SubsidiaryResponse)
def get_subsidiary(
    business_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubsidiaryResponse:
    """Get a single subsidiary's detail."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsidiary not found")
    _require_same_org(current_user, business)

    user_count = db.query(func.count(User.id)).filter(User.business_id == business.id).scalar() or 0
    return SubsidiaryResponse(
        id=business.id, organization_id=business.organization_id, name=business.name,
        email=business.email, phone=business.phone,
        is_primary_subsidiary=business.is_primary_subsidiary, is_active=business.is_active,
        user_count=user_count,
    )


@router.patch("/subsidiaries/{business_id}", response_model=SubsidiaryResponse)
def update_subsidiary(
    business_id: UUID,
    body: SubsidiaryUpdate,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SubsidiaryResponse:
    """Rename/edit a subsidiary's metadata."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsidiary not found")
    _require_same_org(current_user, business)

    if body.name is not None:
        business.name = body.name
    if body.phone is not None:
        business.phone = body.phone

    EventService(db).create_event(
        business_id=business.id,
        event_type=EventType.SUBSIDIARY_UPDATED,
        entity_type="business",
        entity_id=business.id,
        actor_id=current_user.user_id,
        description=f"Subsidiary '{business.name}' updated",
        commit=False,
    )

    db.commit()
    db.refresh(business)

    user_count = db.query(func.count(User.id)).filter(User.business_id == business.id).scalar() or 0
    return SubsidiaryResponse(
        id=business.id, organization_id=business.organization_id, name=business.name,
        email=business.email, phone=business.phone,
        is_primary_subsidiary=business.is_primary_subsidiary, is_active=business.is_active,
        user_count=user_count,
    )


@router.delete("/subsidiaries/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_subsidiary(
    business_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_org_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Soft-deactivate a subsidiary. Hard delete is not exposed given CASCADE blast radius."""
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsidiary not found")
    _require_same_org(current_user, business)

    if business.is_primary_subsidiary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate an organization's primary subsidiary",
        )

    business.is_active = False

    EventService(db).create_event(
        business_id=business.id,
        event_type=EventType.SUBSIDIARY_DEACTIVATED,
        entity_type="business",
        entity_id=business.id,
        actor_id=current_user.user_id,
        description=f"Subsidiary '{business.name}' deactivated",
        commit=False,
    )

    db.commit()
