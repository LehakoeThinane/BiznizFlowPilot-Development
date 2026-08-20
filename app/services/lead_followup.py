"""AI-tailored first-touch follow-up email for automated lead-gen leads (see
app/services/lead_gen_schedule.py). Each lead-gen-sourced Lead only ever
gets one of these, at creation time - the existing external_ref dedup on
Customer already guarantees a given Google Places result is only ever
imported once, so there's no separate "already emailed" tracking needed."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.engine import get_engine
from app.core.config import settings
from app.models.lead import Lead
from app.repositories.customer import CustomerRepository
from app.services.email import send_lead_followup_email

logger = logging.getLogger(__name__)

_SUBJECT_LINE_RE = re.compile(r"^SUBJECT:\s*(.+)$", re.MULTILINE)

_SYSTEM_PROMPT = """You write short, specific first-touch outreach emails on behalf of an IT solutions and web/software company reaching out to a prospective client they found through research - not a mass blast. The recipient never asked for this email, so it has to read like a real person looked at their specific business and had a genuine reason to write, never generic or templated-sounding, no placeholder phrases like "I hope this finds you well" or "I came across your business".

You'll be given the recipient's business name, an ANGLE (either "website" - they have no website, pitch a custom-built one - or "systems" - they already have a website but could benefit from internal automation/systems), and whatever real detail was found about them. Use that detail specifically. If nothing specific was found, keep the email shorter rather than inventing a detail.

Rules:
- Under 120 words.
- No bullet points, no markdown, no clickbait subject line.
- Sign off with the sending company's name only - no fake personal name.
- Include one short, plain sentence offering to stop reaching out if they reply and say so.
- Output format: first line "SUBJECT: <subject line>", a blank line, then the email body only - nothing else."""


@dataclass
class LeadFollowupDraft:
    subject: str
    plain_body: str


def draft_followup_email(business_name: str, lead_name: str, angle: str, context_notes: str) -> LeadFollowupDraft:
    """Ask the AI provider for a tailored draft. Callers are expected to have
    already checked a real provider is configured (see send_followup_to_lead)
    - EchoEngine's placeholder reply would otherwise get parsed as a "body"
    and leak "[AI not configured...]" into a real email."""
    engine = get_engine()
    user_message = (
        f"Sending company: {business_name}\n"
        f"Recipient business: {lead_name}\n"
        f"Angle: {angle}\n"
        f"What we found about them: {context_notes or '(nothing beyond the business name)'}"
    )
    response = engine.chat(messages=[{"role": "user", "content": user_message}], system_prompt=_SYSTEM_PROMPT)
    return _parse_draft(response.reply, lead_name=lead_name, angle=angle)


def _parse_draft(raw: str, lead_name: str, angle: str) -> LeadFollowupDraft:
    """Parse the SUBJECT:-prefixed format _SYSTEM_PROMPT asks for, mirroring
    marketing_blog._parse_full_post's tolerance for a model that doesn't
    follow the format exactly (only Groq has real structured output)."""
    subject_match = _SUBJECT_LINE_RE.search(raw)
    body = _SUBJECT_LINE_RE.sub("", raw, count=1).lstrip("\n ").strip()

    if subject_match and body:
        return LeadFollowupDraft(subject=subject_match.group(1).strip(), plain_body=body)

    pitch = "a website built for you" if angle == "website" else "a look at automating parts of your business"
    fallback_body = (
        f"Hi {lead_name} team,\n\n"
        f"We help businesses like yours with {pitch}. If that's ever useful, happy to chat - "
        f"and if you'd rather not hear from us again, just reply and let us know."
    )
    return LeadFollowupDraft(subject=f"Quick note for {lead_name}", plain_body=fallback_body)


def send_followup_to_lead(
    db: Session, lead: Lead, business_name: str, organization_id: UUID | None
) -> bool:
    """Draft and send the one-time automated follow-up for a lead-gen lead.

    Returns False (no-op, not an error) when there's no email to send to, or
    when no real AI provider is configured - sending a templated email while
    the whole point is "tailored, not generic" would defeat the feature.
    """
    if settings.ai_provider.lower() == "echo":
        logger.warning("lead_followup skipped for lead %s - AI_PROVIDER is not configured", lead.id)
        return False

    customer = CustomerRepository(db).get(lead.business_id, lead.customer_id)
    if customer is None or not customer.email:
        return False

    angle = "website" if lead.source == "google_places_no_website" else "systems"
    draft = draft_followup_email(
        business_name=business_name, lead_name=customer.name, angle=angle, context_notes=lead.notes or "",
    )
    send_lead_followup_email(
        to_email=customer.email,
        subject=draft.subject,
        plain_body=draft.plain_body,
        business_name=business_name,
        db=db,
        organization_id=organization_id,
    )
    return True
