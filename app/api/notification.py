"""Notification API — list, mark read, count."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.notification import Notification
from app.schemas.auth import CurrentUser
from app.schemas.notification import NotificationCount, NotificationListResponse, NotificationOut

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    skip: int = 0,
    limit: int = 30,
    unread_only: bool = False,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    q = db.query(Notification).filter(
        Notification.business_id == current_user.business_id,
        Notification.user_id == current_user.user_id,
    )
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    unread = db.query(sa.func.count(Notification.id)).filter(
        Notification.business_id == current_user.business_id,
        Notification.user_id == current_user.user_id,
        Notification.is_read.is_(False),
    ).scalar() or 0
    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in rows],
        total=total,
        unread=unread,
    )


@router.get("/count", response_model=NotificationCount)
def get_notification_count(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    unread = db.query(sa.func.count(Notification.id)).filter(
        Notification.business_id == current_user.business_id,
        Notification.user_id == current_user.user_id,
        Notification.is_read.is_(False),
    ).scalar() or 0
    total = db.query(sa.func.count(Notification.id)).filter(
        Notification.business_id == current_user.business_id,
        Notification.user_id == current_user.user_id,
    ).scalar() or 0
    return NotificationCount(unread=unread, total=total)


@router.patch("/{notif_id}/read", response_model=NotificationOut)
def mark_read(
    notif_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == current_user.user_id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return NotificationOut.model_validate(notif)


@router.patch("/read-all", status_code=204)
def mark_all_read(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    db.query(Notification).filter(
        Notification.business_id == current_user.business_id,
        Notification.user_id == current_user.user_id,
        Notification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
