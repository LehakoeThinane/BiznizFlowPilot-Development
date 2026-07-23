"""Onboarding checklist step definitions.

Mirrors app/core/entitlements.py's FEATURE_TIERS keys exactly, so a step
only ever appears once the org's plan_tier actually unlocks it - there is
no separate "onboarding tier" concept to keep in sync.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnboardingStep:
    key: str
    required_feature: str | None  # None = available at every tier


STEP_DEFINITIONS: list[OnboardingStep] = [
    OnboardingStep("invite_team", None),
    OnboardingStep("add_first_lead", None),
    OnboardingStep("set_up_inventory", None),
    OnboardingStep("explore_finance", "finance"),
    OnboardingStep("set_up_automation", "workflow_automation"),
    OnboardingStep("try_ai_copilot", "ai_chat"),
    OnboardingStep("set_up_hr", "hr"),
    OnboardingStep("add_subsidiary", "multi_subsidiary"),
]
