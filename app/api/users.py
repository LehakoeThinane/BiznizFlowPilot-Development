"""User API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import CurrentUser
from app.schemas.user import UserListResponse, UserResponse

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
)


@router.get("", response_model=UserListResponse)
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """List active users for the current tenant.

    Used by UI assignment controls (task assignee dropdowns).
    """
    safe_limit = max(1, min(limit, settings.max_page_size))

    query = db.query(User).filter(
        User.business_id == current_user.business_id,
        User.is_active.is_(True),
    )
    total = query.count()
    items = (
        query.order_by(User.first_name.asc(), User.last_name.asc(), User.email.asc())
        .offset(skip)
        .limit(safe_limit)
        .all()
    )

    return UserListResponse(
        total=total,
        items=[UserResponse.model_validate(user) for user in items],
    )
