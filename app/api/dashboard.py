"""Dashboard KPI API route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import PRIVILEGED_ROLES
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    if current_user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Owner or manager required")
    return DashboardService(db).get_dashboard(current_user.business_id)
