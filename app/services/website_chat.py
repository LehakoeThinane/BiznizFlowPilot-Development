"""MM Nexus website chat widget service - an AI answers a visitor first,
a human takes over just by replying normally in BFP's existing
team-messaging feature (see app/services/messaging.py). No new "takeover"
mechanism exists - see the ai_active flip in MessagingService.send_message.

MM Nexus runs as a real business/tenant inside BFP itself, so this is
single-target (settings.mm_nexus_business_id), not a multi-tenant system.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.action_types import EngineResponse
from app.ai.engine import get_engine
from app.core.config import settings
from app.core.security import hash_password
from app.models.messaging import Conversation, Message
from app.models.user import User
from app.models.website_chat_session import WebsiteChatSession
from app.repositories.messaging import ConversationRepository
from app.repositories.user import UserRepository
from app.repositories.website_chat_session import WebsiteChatSessionRepository
from app.services.marketing_blog import _MM_NEXUS_GROUNDING

VISITOR_MARKER_EMAIL = "website-chat@internal.mmnexus.co.za"

_SYSTEM_PROMPT = f"""You are the AI assistant answering visitor questions on MM Nexus's \
website chat widget. Be direct and helpful, in the same tone as the rest of MM Nexus's \
site - conversational, not corporate marketing-speak.

Respond in whichever language the visitor writes in - South Africa has 11 official \
languages (English, Afrikaans, isiZulu, isiXhosa, Sepedi, Setswana, Sesotho, Xitsonga, \
siSwati, Tshivenda, isiNdebele), and you should reply fluently in any of them. If you're \
not confident you're getting a less-common one right, say so plainly rather than guessing \
confidently, and mention a team member will follow up.

If a question genuinely needs a real person (pricing negotiation, something you don't \
know, a complaint), say a team member will follow up - don't invent an answer.

{_MM_NEXUS_GROUNDING}"""


class WebsiteChatNotConfiguredError(Exception):
    """Raised when mm_nexus_business_id/mm_nexus_chat_assignee_user_id aren't set."""


def _require_config() -> tuple[UUID, UUID]:
    if not (settings.mm_nexus_business_id and settings.mm_nexus_chat_assignee_user_id):
        raise WebsiteChatNotConfiguredError("The website chat widget is not configured.")
    return UUID(settings.mm_nexus_business_id), UUID(settings.mm_nexus_chat_assignee_user_id)


def get_or_create_visitor_user(db: Session, business_id: UUID) -> User:
    users = UserRepository(db)
    visitor = users.get_by_email(business_id, VISITOR_MARKER_EMAIL)
    if visitor:
        return visitor

    visitor = users.create(
        business_id=business_id,
        email=VISITOR_MARKER_EMAIL,
        first_name="Website",
        last_name="Visitor",
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        role="staff",
        is_active=True,
    )
    db.refresh(visitor)
    return visitor


def _get_or_create_session(db: Session, token: str | None) -> tuple[WebsiteChatSession, Conversation]:
    business_id, assignee_id = _require_config()
    sessions = WebsiteChatSessionRepository(db)

    if token:
        session = sessions.get_by_token(token)
        if session:
            return session, session.conversation

    visitor = get_or_create_visitor_user(db, business_id)
    repo = ConversationRepository(db)
    conversation = repo.create(business_id=business_id, source="website_widget")
    repo.add_participant(conversation.id, visitor.id)
    repo.add_participant(conversation.id, assignee_id)
    db.commit()
    db.refresh(conversation)

    session = sessions.create(token=token or secrets.token_urlsafe(32), conversation_id=conversation.id)
    db.commit()
    db.refresh(session)
    return session, conversation


def send_visitor_message(db: Session, token: str | None, text: str) -> tuple[str, list[Message]]:
    """Write the visitor's message, and - if a human hasn't taken over yet -
    an AI reply. Returns (session_token, new_messages) so a first-ever call
    with no token gets one back to store."""
    session, conversation = _get_or_create_session(db, token)
    repo = ConversationRepository(db)
    visitor = get_or_create_visitor_user(db, conversation.business_id)

    new_messages = [repo.add_message(conversation.id, visitor.id, text)]

    if conversation.ai_active:
        history = repo.list_messages(conversation.id, limit=settings.ai_conversation_history_limit)
        llm_messages = [
            {"role": "assistant" if m.is_ai_reply else "user", "content": m.content}
            for m in history
            if m.content
        ]
        engine = get_engine()
        try:
            result = engine.chat(llm_messages, _SYSTEM_PROMPT)
        except Exception as exc:
            result = EngineResponse(reply=f"[AI error: {exc}]")
        new_messages.append(repo.add_message(conversation.id, visitor.id, result.reply, is_ai_reply=True))

    db.commit()
    for m in new_messages:
        db.refresh(m)
    return session.token, new_messages


def list_new_messages(db: Session, token: str, since: datetime | None) -> list[Message]:
    session = WebsiteChatSessionRepository(db).get_by_token(token)
    if not session:
        raise WebsiteChatNotConfiguredError("Unknown session token.")
    repo = ConversationRepository(db)
    return repo.list_messages(session.conversation_id, since=since)
