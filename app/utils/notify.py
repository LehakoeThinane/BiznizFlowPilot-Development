"""Notification creation utility — fires notifications to business users."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


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
