"""Onboarding checklist response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class OnboardingStepResponse(BaseModel):
    key: str
    done: bool


class OnboardingChecklistResponse(BaseModel):
    steps: list[OnboardingStepResponse]


class OnboardingHelpRequest(BaseModel):
    note: str | None = None
