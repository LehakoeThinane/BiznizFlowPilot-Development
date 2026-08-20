"""Tests for app/services/lead_followup.py - AI-drafted, one-time follow-up
email for automated lead-gen leads."""

from __future__ import annotations

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.ai.action_types import EngineResponse
from app.models.customer import Customer
from app.models.lead import Lead
from app.services.lead_followup import (
    LeadFollowupDraft,
    _parse_draft,
    draft_followup_email,
    send_followup_to_lead,
)


class TestParseDraft:
    def test_well_formatted_reply_parses_subject_and_body(self):
        raw = "SUBJECT: Quick idea for Acme Plumbing\n\nHi there, saw you don't have a site yet..."

        draft = _parse_draft(raw, lead_name="Acme Plumbing", angle="website")

        assert draft.subject == "Quick idea for Acme Plumbing"
        assert draft.plain_body == "Hi there, saw you don't have a site yet..."

    def test_malformed_reply_falls_back_without_leaking_placeholder_text(self):
        raw = "[AI not configured — set AI_PROVIDER in .env]\n\nYou said: ..."

        draft = _parse_draft(raw, lead_name="Acme Plumbing", angle="website")

        assert "AI not configured" not in draft.plain_body
        assert "AI not configured" not in draft.subject
        assert "Acme Plumbing" in draft.plain_body


class TestDraftFollowupEmail:
    def test_uses_configured_engine_and_parses_its_reply(self):
        fake_engine = Mock()
        fake_engine.chat.return_value = EngineResponse(reply="SUBJECT: Hello\n\nBody text here.")

        with patch("app.services.lead_followup.get_engine", return_value=fake_engine):
            draft = draft_followup_email(
                business_name="MM Nexus", lead_name="Acme Plumbing", angle="systems", context_notes="Has a website"
            )

        assert draft == LeadFollowupDraft(subject="Hello", plain_body="Body text here.")
        call_kwargs = fake_engine.chat.call_args.kwargs
        assert "Acme Plumbing" in call_kwargs["messages"][0]["content"]
        assert "systems" in call_kwargs["messages"][0]["content"]


class TestSendFollowupToLead:
    def _lead_and_customer(self, test_db: Session, business_id, source: str, email: str | None) -> Lead:
        customer = Customer(id=uuid4(), business_id=business_id, name="Acme Plumbing", email=email)
        test_db.add(customer)
        test_db.commit()
        lead = Lead(id=uuid4(), business_id=business_id, customer_id=customer.id, source=source, status="new")
        test_db.add(lead)
        test_db.commit()
        return lead

    def test_skips_when_ai_provider_not_configured(self, test_db: Session, owner_user):
        lead = self._lead_and_customer(
            test_db, owner_user.business_id, "google_places_no_website", "prospect@example.com"
        )

        with patch("app.services.lead_followup.settings.ai_provider", "echo"):
            sent = send_followup_to_lead(test_db, lead, "MM Nexus", None)

        assert sent is False

    def test_skips_when_lead_has_no_email(self, test_db: Session, owner_user):
        lead = self._lead_and_customer(test_db, owner_user.business_id, "google_places_no_website", None)

        with patch("app.services.lead_followup.settings.ai_provider", "groq"):
            sent = send_followup_to_lead(test_db, lead, "MM Nexus", None)

        assert sent is False

    def test_sends_with_website_angle_for_no_website_leads(self, test_db: Session, owner_user):
        lead = self._lead_and_customer(
            test_db, owner_user.business_id, "google_places_no_website", "prospect@example.com"
        )

        with patch("app.services.lead_followup.settings.ai_provider", "groq"), \
             patch("app.services.lead_followup.draft_followup_email") as mock_draft, \
             patch("app.services.lead_followup.send_lead_followup_email") as mock_send:
            mock_draft.return_value = LeadFollowupDraft(subject="Subj", plain_body="Body")
            sent = send_followup_to_lead(test_db, lead, "MM Nexus", None)

        assert sent is True
        assert mock_draft.call_args.kwargs["angle"] == "website"
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["to_email"] == "prospect@example.com"

    def test_sends_with_systems_angle_for_has_website_leads(self, test_db: Session, owner_user):
        lead = self._lead_and_customer(
            test_db, owner_user.business_id, "google_places_has_website", "prospect@example.com"
        )

        with patch("app.services.lead_followup.settings.ai_provider", "groq"), \
             patch("app.services.lead_followup.draft_followup_email") as mock_draft, \
             patch("app.services.lead_followup.send_lead_followup_email"):
            mock_draft.return_value = LeadFollowupDraft(subject="Subj", plain_body="Body")
            send_followup_to_lead(test_db, lead, "MM Nexus", None)

        assert mock_draft.call_args.kwargs["angle"] == "systems"


class TestSendLeadFollowupEmailIntegration:
    def test_dev_mode_send_does_not_raise(self, test_db: Session):
        """No Resend/SMTP configured in tests - this exercises the real
        html-escaping/paragraph-wrapping path, just logging instead of
        actually delivering (see email.py's dev_mode branch)."""
        from app.services.email import send_lead_followup_email

        send_lead_followup_email(
            to_email="prospect@example.com",
            subject="Quick note",
            plain_body="First paragraph with a <tag> in it.\n\nSecond paragraph.",
            business_name="MM Nexus",
        )
