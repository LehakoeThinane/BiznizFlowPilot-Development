"""Notification creation utility — fires notifications to business users."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.repositories.user import UserRepository


def notify_business(
    db: Session,
    business_id: UUID,
    type_: str,
    title: str,
    message: str,
    action_url: str | None = None,
    related_type: str | None = None,
    related_id: UUID | None = None,
    roles: tuple[str, ...] = ("owner", "manager"),
) -> None:
    """Queue a notification for every active user with matching roles in the business.

    Does NOT commit — the caller commits after adding business records so
    both end up in the same transaction.
    """
    users = (
        db.query(User)
        .filter(
            User.business_id == business_id,
            User.role.in_(roles),
            User.is_active.is_(True),
        )
        .all()
    )
    for user in users:
        db.add(
            Notification(
                id=uuid4(),
                business_id=business_id,
                user_id=user.id,
                type=type_,
                title=title,
                message=message,
                action_url=action_url,
                related_type=related_type,
                related_id=related_id,
                is_read=False,
            )
        )


def notify_organization_role(
    db: Session,
    organization_id: UUID,
    role: str,
    type_: str,
    title: str,
    message: str,
    action_url: str | None = None,
    related_type: str | None = None,
    related_id: UUID | None = None,
) -> None:
    """Queue a notification for every active user with a given role across
    every subsidiary in an organization.

    IT Admins (and other org-wide roles) aren't scoped to a single
    business_id the way notify_business assumes - use this instead when the
    audience spans the organization's subsidiaries. Same sanctioned
    business_id-bypass as UserRepository.count_active_in_organization.

    Does NOT commit — same contract as notify_business.
    """
    users = UserRepository(db).list_by_role_in_organization(organization_id, role)
    for user in users:
        db.add(
            Notification(
                id=uuid4(),
                business_id=user.business_id,
                user_id=user.id,
                type=type_,
                title=title,
                message=message,
                action_url=action_url,
                related_type=related_type,
                related_id=related_id,
                is_read=False,
            )
        )


def notify_user(
    db: Session,
    business_id: UUID,
    user_id: UUID,
    type_: str,
    title: str,
    message: str,
    action_url: str | None = None,
    related_type: str | None = None,
    related_id: UUID | None = None,
) -> None:
    """Queue a notification for one specific user - for instant, targeted
    alerts (e.g. "a new lead was assigned to you") rather than the
    broadcast-to-a-role shape of notify_business.

    Does NOT commit — same contract as notify_business.
    """
    db.add(
        Notification(
            id=uuid4(),
            business_id=business_id,
            user_id=user_id,
            type=type_,
            title=title,
            message=message,
            action_url=action_url,
            related_type=related_type,
            related_id=related_id,
            is_read=False,
        )
    )
