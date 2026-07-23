"""Onboarding checklist API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.onboarding import OnboardingChecklistResponse, OnboardingHelpRequest
from app.services.onboarding import OnboardingService

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingChecklistResponse)
def get_checklist(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingChecklistResponse:
    return OnboardingService(db).get_checklist(current_user)


@router.post("/help", status_code=204)
def request_help(
    body: OnboardingHelpRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Request onboarding assistance - available to every plan tier, not
    gated by FEATURE_TIERS, since this is about setup help rather than a
    paid feature."""
    OnboardingService(db).request_help(current_user, body.note)
