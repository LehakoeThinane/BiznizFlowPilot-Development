"""Metrics API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.metrics import MetricsResponse
from app.services.metrics import MetricsService

router = APIRouter(
    prefix="/api/v1/metrics",
    tags=["metrics"],
)


@router.get("", response_model=MetricsResponse)
def get_metrics(
    business_id: UUID | None = None,
    current_user: Annotated[CurrentUser, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """Return aggregate workflow metrics scoped to the caller's tenant."""
    requested_business_id = business_id or current_user.business_id
    if requested_business_id != current_user.business_id:
        raise HTTPException(status_code=403, detail="Cannot access metrics for another business")

    return MetricsService(db).get_metrics(requested_business_id)

