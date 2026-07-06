"""User invitation API routes - domain-restricted employee onboarding."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import EventType
from app.core.permissions import INVITE_MANAGERS
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.invitation import InvitationCreate, InvitationListResponse, InvitationResponse
from app.services.event import EventService
from app.services.invitation import InvitationService

router = APIRouter(prefix="/api/v1/users", tags=["invites"])
limiter = Limiter(key_func=get_remote_address)


def _resolve_target_business_id(current_user: CurrentUser, body: InvitationCreate) -> UUID:
    """Owner/manager can only invite into their own business; it_admin may target
    any subsidiary in their own organization (validated by the caller)."""
    if current_user.role == "it_admin":
        if body.business_id is None:
            return current_user.business_id
        return body.business_id
    return current_user.business_id


@router.post("/invite", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_invitation(
    request: Request,
    body: InvitationCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationResponse:
    """Invite someone to join a business. Owner/manager/it_admin only."""
    if current_user.role not in INVITE_MANAGERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner, manager, or IT Admin can send invitations",
        )

    target_business_id = _resolve_target_business_id(current_user, body)

    if current_user.role != "it_admin" and target_business_id != current_user.business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot invite into another business")

    from app.models.business import Business

    target_business = db.query(Business).filter(Business.id == target_business_id).first()
    if not target_business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    if current_user.role == "it_admin" and str(target_business.organization_id) != str(current_user.organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Business is not in your organization")

    service = InvitationService(db)
    try:
        invitation, raw_token = service.create_invitation(
            business_id=target_business_id,
            organization_id=target_business.organization_id,
            email=body.email,
            role=body.role,
            invited_by=current_user.user_id,
            inviter_role=current_user.role,
            inviter_name=current_user.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    from app.services.email import send_invite_email

    org_name, business_name = service.get_display_context(invitation)
    try:
        send_invite_email(
            to_email=body.email,
            organization_name=org_name,
            business_name=business_name,
            invited_by_name=current_user.full_name,
            raw_token=raw_token,
        )
    except Exception:
        pass  # email delivery failure is logged inside send_invite_email

    # The invitation itself is already committed above (create_invitation),
    # and send_invite_email is an external network call - true one-transaction
    # atomicity with the audit event isn't practical here. What matters is not
    # silently losing the event on failure, so this is intentionally not swallowed.
    EventService(db).create_event(
        business_id=target_business_id,
        event_type=EventType.USER_INVITED,
        entity_type="user_invitation",
        entity_id=invitation.id,
        actor_id=current_user.user_id,
        description=f"Invited {body.email} as {body.role}",
    )

    return InvitationResponse.model_validate(invitation)


@router.get("/invites", response_model=InvitationListResponse)
def list_invitations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = 0,
    limit: int = 50,
) -> InvitationListResponse:
    """List invitations - own business for owner/manager, org-wide for it_admin."""
    service = InvitationService(db)
    if current_user.role == "it_admin":
        items = service.invite_repo.list_for_organization(
            UUID(str(current_user.organization_id)), skip=skip, limit=limit
        )
        total = len(items)
    elif current_user.role in ("owner", "manager"):
        items = service.invite_repo.list(UUID(str(current_user.business_id)), skip=skip, limit=limit)
        total = service.invite_repo.count(UUID(str(current_user.business_id)))
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return InvitationListResponse(
        total=total,
        items=[InvitationResponse.model_validate(i) for i in items],
    )


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invite_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Revoke a pending invitation."""
    if current_user.role not in INVITE_MANAGERS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    service = InvitationService(db)
    if current_user.role == "it_admin":
        revoked = service.revoke_invitation(
            invite_id, organization_id=UUID(str(current_user.organization_id))
        )
    else:
        revoked = service.revoke_invitation(invite_id, business_id=current_user.business_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    # The revocation itself is already committed above (revoke_invitation) -
    # not swallowing this so a failed audit event surfaces instead of vanishing.
    EventService(db).create_event(
        business_id=current_user.business_id,
        event_type=EventType.USER_INVITE_REVOKED,
        entity_type="user_invitation",
        entity_id=invite_id,
        actor_id=current_user.user_id,
        description="Invitation revoked",
    )
