"""Onboarding checklist - computed on-the-fly from existing data, nothing
persisted. A step's "done" state is always re-derived from real records
(invites sent, leads added, etc.), never cached.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.entitlements import FEATURE_TIERS, FULL_ACCESS_TIERS
from app.core.onboarding import STEP_DEFINITIONS
from app.models.business import Business
from app.models.chat import ChatConversation, ChatMessage
from app.models.finance import Expense
from app.models.hr import Employee
from app.models.organization import Organization
from app.models.workflow import WorkflowDefinition
from app.repositories.invitation import InvitationRepository
from app.repositories.lead import LeadRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.schemas.auth import CurrentUser
from app.schemas.onboarding import OnboardingChecklistResponse, OnboardingStepResponse
from app.services.email import send_onboarding_help_request_email


class OnboardingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_checklist(self, current_user: CurrentUser) -> OnboardingChecklistResponse:
        org = self._resolve_org(current_user)
        business_id = current_user.business_id

        steps = [
            step
            for step in STEP_DEFINITIONS
            if step.required_feature is None
            or org.plan_tier in FULL_ACCESS_TIERS
            or org.plan_tier in FEATURE_TIERS.get(step.required_feature, frozenset())
        ]

        done_checks = {
            "invite_team": lambda: (
                UserRepository(self.db).count_active_in_organization(org.id)
                + InvitationRepository(self.db).count_pending_for_organization(org.id)
                > 1
            ),
            "add_first_lead": lambda: LeadRepository(self.db).count(business_id) > 0,
            "set_up_inventory": lambda: ProductRepository(self.db).count(business_id) > 0,
            "explore_finance": lambda: (
                self.db.query(Expense).filter(Expense.business_id == business_id).first() is not None
            ),
            "set_up_automation": lambda: (
                self.db.query(WorkflowDefinition)
                .filter(WorkflowDefinition.business_id == business_id, WorkflowDefinition.deleted_at.is_(None))
                .first()
                is not None
            ),
            "try_ai_copilot": lambda: (
                self.db.query(ChatMessage)
                .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
                .filter(ChatConversation.business_id == business_id)
                .first()
                is not None
            ),
            "set_up_hr": lambda: (
                self.db.query(Employee).filter(Employee.business_id == business_id).first() is not None
            ),
            "add_subsidiary": lambda: (
                self.db.query(Business).filter(Business.organization_id == org.id).count() > 1
            ),
        }

        return OnboardingChecklistResponse(
            steps=[
                OnboardingStepResponse(key=step.key, done=done_checks[step.key]())
                for step in steps
            ]
        )

    def request_help(self, current_user: CurrentUser, note: str | None) -> None:
        """Notify staff that a customer wants help onboarding - available to
        every tier, deliberately not gated by FEATURE_TIERS."""
        business = self.db.query(Business).filter(Business.id == current_user.business_id).first()
        send_onboarding_help_request_email(
            user_name=current_user.full_name,
            user_email=current_user.email,
            business_name=business.name if business else "Unknown business",
            note=note,
        )

    def _resolve_org(self, current_user: CurrentUser) -> Organization:
        org = (
            OrganizationRepository(self.db).get_by_id(current_user.organization_id)
            if current_user.organization_id
            else None
        )
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No organization on this account - cannot load onboarding checklist.",
            )
        return org
